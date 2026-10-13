// Bound buffering in the authenticated proxy, including chunked uploads.
export async function readLimitedBody(request: Request): Promise<ArrayBuffer> {
  const limit = request.headers.get("content-type")?.startsWith("multipart/form-data")
    ? 5 * 1024 * 1024 + 64 * 1024
    : 1024 * 1024;
  if (Number(request.headers.get("content-length")) > limit) throw new RangeError("Request too large");
  if (!request.body) return new ArrayBuffer(0);
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > limit) {
        await reader.cancel();
        throw new RangeError("Request too large");
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const body = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.byteLength; }
  return body.buffer;
}
