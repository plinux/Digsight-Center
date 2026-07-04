import {readFile} from "node:fs/promises";

export async function importSourceModule(path, replacements = []) {
  let source = await readFile(path, "utf8");
  for (const [target, replacement] of replacements) {
    source = source.replace(target, replacement);
  }
  const encoded = Buffer.from(source, "utf8").toString("base64");
  return import(`data:text/javascript;base64,${encoded}`);
}
