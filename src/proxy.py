"""A generic HTTP forward proxy (GET only).

Design
- Inbound: a raw asyncio TCP server. We parse the request line + headers by hand
  because a forward proxy receives the destination in "absolute-form"
  (GET http://host/path), which higher-level frameworks hide from us.
- Outbound: httpx in async mode, so waiting on a slow destination never blocks
  the event loop that is serving every other client.
- Headers: hop-by-hop headers are stripped in both directions. On the response we
  also recompute Content-Length (and drop Content-Encoding/Transfer-Encoding),
  because httpx hands us the already-decoded body.
- Body is kept as raw bytes end to end, so binary payloads pass through
  untouched.

"""

import asyncio
from http import HTTPStatus
import httpx


# decisions of address and port for the proxy server inbound traffic
HOST = "127.0.0.1"
PORT = 43210

# Give up on a slow destination so one stuck request can't leak a connection.
UPSTREAM_TIMEOUT = 30.0

# Cap on the request line + headers block we're willing to read from the client.
MAX_REQUEST_HEADER_BYTES = 64 * 1024

# Hop-by-hop headers describe a single connection, not the whole message, so we
# never forward them (RFC 7230 6.1).
HOP_BY_HOP = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}

# Headers we also strip. Outgoing: content-length (the request body is empty).
# Incoming: content-length and content-encoding, because httpx already decoded
# the body, so the original size/compression no longer match what we forward.
REQUEST_DROP = HOP_BY_HOP | {"content-length"}
RESPONSE_DROP = HOP_BY_HOP | {"content-length", "content-encoding"}


async def _send_simple(writer: asyncio.StreamWriter, status: int, message: str) -> None:
    """Send a minimal plain-text response (used for proxy-generated errors)."""
    # Body is our own text content: encode as utf-8 and declare it via charset.
    body = message.encode("utf-8")
    reason = HTTPStatus(status).phrase
    # Head is HTTP framing: it must be latin-1 (1 character = 1 byte on the wire).
    head = (
        f"HTTP/1.1 {status} {reason}\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        f"Content-Length: {len(body)}\r\n"
        "Connection: close\r\n"
        "\r\n"
    ).encode("latin-1")
    writer.write(head + body)
    await writer.drain()


def _parse_request(raw: bytes) -> tuple[str, str, dict[str, str]]:
    """Parse the request line + headers. Raises ValueError on malformed input."""
    text = raw.decode("latin-1")
    lines = text.split("\r\n")

    # The first line is the request line: "METHOD TARGET VERSION".
    parts = lines[0].split(" ")
    if len(parts) != 3:
        raise ValueError("malformed request line")
    method, target, _version = parts

    # The remaining lines are "Name: value" headers (blank lines are skipped).
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        if ":" not in line:
            raise ValueError("malformed header line")
        name, value = line.split(":", 1)
        headers[name.strip()] = value.strip()

    return method, target, headers


async def handle_client(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    client: httpx.AsyncClient,
) -> None:
    try:
        # We have no web framework here, so we read the raw connection ourselves.
        # A request head ends at the first blank line, so read up to that marker.
        try:
            raw = await reader.readuntil(b"\r\n\r\n")
        except asyncio.IncompleteReadError:
            return  # client hung up before sending a complete request
        except asyncio.LimitOverrunError:
            await _send_simple(writer, 431, "request headers too large")
            return

        # Turn the raw bytes into a method, a target URL, and a headers dict.
        try:
            method, target, headers = _parse_request(raw)
        except ValueError:
            await _send_simple(writer, 400, "malformed request")
            return

        # A proxy request must carry an absolute-form target (the full URL).
        if not target.lower().startswith(("http://", "https://")):
            await _send_simple(writer, 400, "proxy requires an absolute-form URL")
            return

        # Forward the client's headers, minus the ones that must not be relayed.
        forward_headers = {
            name: value
            for name, value in headers.items()
            if name.lower() not in REQUEST_DROP
        }

        # Fetch the real resource on the client's behalf.
        try:
            response = await client.request(
                method,
                target,
                headers=forward_headers,
                timeout=UPSTREAM_TIMEOUT,
            )
        except httpx.TimeoutException:
            await _send_simple(writer, 504, "destination timed out")
            return
        except httpx.RequestError:
            await _send_simple(writer, 502, "could not reach destination")
            return

        body = response.content  # already-decoded bytes

        # Rebuild the response head: status line, then the destination's headers
        # (minus the ones we must drop), then our own framing headers.
        out = [f"HTTP/1.1 {response.status_code} {response.reason_phrase}\r\n"]
        for name, value in response.headers.items():
            if name.lower() in RESPONSE_DROP:
                continue
            out.append(f"{name}: {value}\r\n")
        out.append(f"Content-Length: {len(body)}\r\n")
        out.append("Connection: close\r\n")
        out.append("\r\n")

        # Send the head as text, then the body as untouched bytes (binary-safe).
        writer.write("".join(out).encode("latin-1"))
        writer.write(body)
        await writer.drain()
    except Exception:
        # One bad request must never take down the whole proxy.
        pass
    finally:
        # Always hang up this connection, whether we succeeded or failed.
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass


async def main() -> None:
    # One shared client for all requests; pass redirects back instead of following them.
    async with httpx.AsyncClient(follow_redirects=False) as client:
        server = await asyncio.start_server(
            lambda reader, writer: handle_client(reader, writer, client),
            HOST,
            PORT,
            limit=MAX_REQUEST_HEADER_BYTES,
        )
        print(f"Forward proxy listening on {HOST}:{PORT}")
        async with server:
            await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
