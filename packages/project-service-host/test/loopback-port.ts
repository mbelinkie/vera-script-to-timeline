import { createServer as createTcpServer } from "node:net";

/** Choose a genuine ephemeral loopback port, then close probe before test bind. */
export async function unusedLoopbackPort(): Promise<number> {
  const probe = createTcpServer();
  await new Promise<void>((resolve) => { probe.listen(0, "127.0.0.1", resolve); });
  const addr = probe.address();
  if (!addr || typeof addr === "string") throw new Error("no port");
  await new Promise<void>((resolve) => { probe.close(() => resolve()); });
  return addr.port;
}
