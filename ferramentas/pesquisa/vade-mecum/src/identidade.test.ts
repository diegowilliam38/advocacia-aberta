import { expect, test } from "bun:test";
import type { IncomingMessage } from "node:http";

import { familiaDoCliente, identificarAtor } from "./identidade.js";

/** Requisição mínima: só os headers importam para a identificação. */
function req(headers: Record<string, string>): IncomingMessage {
  return { headers } as unknown as IncomingMessage;
}

test("usuário do ChatGPT/Codex é identificado pelo subject, não pelo IP", () => {
  const ator = identificarAtor(
    req({ "user-agent": "openai-mcp/1.0.0 (Codex)", "x-openai-subject": "v1/ABC" }),
    "203.0.113.7",
  );
  expect(ator.chave).toBe("openai:v1/ABC");
  expect(ator.origem).toBe("openai-subject");
  expect(ator.cliente).toBe("Codex");
  expect(ator.identificaPessoa).toBe(true);
});

test("mesmo IP com subjects diferentes gera atores diferentes", () => {
  const cabecalho = { "user-agent": "openai-mcp/1.0.0" };
  const a = identificarAtor(req({ ...cabecalho, "x-openai-subject": "v1/AAA" }), "203.0.113.7");
  const b = identificarAtor(req({ ...cabecalho, "x-openai-subject": "v1/BBB" }), "203.0.113.7");
  expect(a.chave).not.toBe(b.chave);
});

test("mesmo subject em IPs diferentes continua sendo o mesmo ator", () => {
  const cabecalho = { "user-agent": "openai-mcp/1.0.0", "x-openai-subject": "v1/AAA" };
  expect(identificarAtor(req(cabecalho), "203.0.113.7").chave).toBe(
    identificarAtor(req(cabecalho), "198.51.100.2").chave,
  );
});

test("claude.ai cai para IP e é marcado como origem compartilhada", () => {
  // Todos os usuários do claude.ai chegam pelo IP da Anthropic: somar esse consumo
  // como se fosse de uma pessoa inventaria um heavy user que não existe.
  const ator = identificarAtor(req({ "user-agent": "Claude-User" }), "160.79.106.10");
  expect(ator.chave).toBe("ip:160.79.106.10");
  expect(ator.origem).toBe("ip");
  expect(ator.identificaPessoa).toBe(false);
});

test("Claude Code cai para IP, mas o IP é da pessoa", () => {
  const ator = identificarAtor(req({ "user-agent": "claude-code/2.1.216 (cli)" }), "191.177.143.9");
  expect(ator.chave).toBe("ip:191.177.143.9");
  expect(ator.identificaPessoa).toBe(true);
});

test("subject vazio não vira ator identificado", () => {
  const ator = identificarAtor(
    req({ "user-agent": "openai-mcp/1.0.0", "x-openai-subject": "" }),
    "203.0.113.7",
  );
  expect(ator.chave).toBe("ip:203.0.113.7");
  expect(ator.origem).toBe("ip");
});

test("famílias de cliente reconhecidas", () => {
  expect(familiaDoCliente("openai-mcp/1.0.0 (Codex)")).toBe("Codex");
  expect(familiaDoCliente("openai-mcp/1.0.0")).toBe("ChatGPT");
  expect(familiaDoCliente("Claude-User")).toBe("claude.ai");
  expect(familiaDoCliente("claude-code/2.1.216 (cli)")).toBe("Claude Code");
  expect(familiaDoCliente("")).toBe("(sem identificação)");
  expect(familiaDoCliente("Mozilla/5.0")).toBe("outro");
});
