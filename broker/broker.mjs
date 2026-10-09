import { createServer } from "node:net";
import { Aedes } from "aedes";

const host = "127.0.0.1";
const port = 1884;
const broker = await Aedes.createBroker();
const server = createServer(broker.handle);

server.listen(port, host, () => {
  console.log(`Local MQTT broker listening on ${host}:${port}`);
});

server.on("error", (error) => {
  console.error(`Local MQTT broker failed: ${error.message}`);
  process.exitCode = 1;
});

async function shutdown() {
  server.close();
  await broker.close();
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
