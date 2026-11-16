// Pruebas del Worker con un KV en memoria: node --test edge/estado/test/
import { test } from "node:test";
import assert from "node:assert/strict";
import worker, { estadoDe, mismoToken, validarPublicacion } from "../src/index.js";

const TOKEN = "secreto-de-prueba-123";

function entorno() {
  const datos = new Map();
  return {
    TOKEN_PUBLICACION: TOKEN,
    escrituras: 0,
    ESTADO: {
      async get(clave, opciones) {
        const v = datos.get(clave);
        return v == null ? null : opciones?.type === "json" ? JSON.parse(v) : v;
      },
      async put(clave, valor) { this._env.escrituras++; datos.set(clave, valor); },
    },
  };
}

function estado(nivel = "SIN_PROBLEMAS", extra = {}) {
  return { generadoEn: "2026-11-15T20:00:00Z", alcance: "GLOBAL", nivel, mensaje: "m", serie: [], totales: {}, tipos: [],
           zonas: [], colectivos: [], ...extra };
}

function publicacion() {
  return { version: 1, publicadoEn: new Date().toISOString(),
           estados: { GLOBAL: estado("PROBLEMAS"), "ZONA-05": estado("PROBLEMAS", { alcance: "ZONA-05" }) } };
}

async function pedir(env, metodo, ruta, { cuerpo, token } = {}) {
  env.ESTADO._env = env;
  const headers = { "content-type": "application/json" };
  if (token) headers.authorization = `Bearer ${token}`;
  return worker.fetch(new Request(`https://espejo.example${ruta}`, {
    method: metodo, headers, body: cuerpo === undefined ? undefined : JSON.stringify(cuerpo),
  }), env);
}

test("sin publicación previa el estado responde 503", async () => {
  const r = await pedir(entorno(), "GET", "/api/estado");
  assert.equal(r.status, 503);
});

test("publicar exige el token", async () => {
  const env = entorno();
  assert.equal((await pedir(env, "PUT", "/publicar", { cuerpo: publicacion() })).status, 401);
  assert.equal((await pedir(env, "PUT", "/publicar", { cuerpo: publicacion(), token: "otro" })).status, 401);
  assert.equal(env.escrituras, 0);
});

test("publica y sirve el estado global y de zona, marcado como respaldo", async () => {
  const env = entorno();
  const r = await pedir(env, "PUT", "/publicar", { cuerpo: publicacion(), token: TOKEN });
  assert.equal(r.status, 200);
  assert.equal(env.escrituras, 1);

  const g = await (await pedir(env, "GET", "/api/estado")).json();
  assert.equal(g.nivel, "PROBLEMAS");
  assert.equal(g.respaldo.fuente, "cloudflare");

  const z = await pedir(env, "GET", "/api/estado?zonaId=ZONA-05");
  assert.equal(z.status, 200);
  assert.equal(z.headers.get("access-control-allow-origin"), "*");
  assert.equal((await z.json()).alcance, "ZONA-05");

  assert.equal((await pedir(env, "GET", "/api/estado?zonaId=ZONA-99")).status, 404);
  assert.equal((await pedir(env, "GET", "/api/estado?zonaId=<script>")).status, 404);
});

test("rechaza publicaciones mal formadas sin escribir", async () => {
  const env = entorno();
  for (const malo of [{}, { version: 2 }, { version: 1, publicadoEn: "x", estados: {} },
                      { version: 1, publicadoEn: "x", estados: { GLOBAL: estado(), "../x": estado() } }]) {
    assert.equal((await pedir(env, "PUT", "/publicar", { cuerpo: malo, token: TOKEN })).status, 400);
  }
  assert.equal(env.escrituras, 0);
});

test("solo PUT publica y el resto de rutas es de lectura", async () => {
  const env = entorno();
  assert.equal((await pedir(env, "GET", "/publicar")).status, 405);
  assert.equal((await pedir(env, "POST", "/api/estado", { cuerpo: {} })).status, 405);
  assert.equal((await pedir(env, "GET", "/no-existe")).status, 404);
});

test("salud y página propia", async () => {
  const env = entorno();
  await pedir(env, "PUT", "/publicar", { cuerpo: publicacion(), token: TOKEN });
  const s = await (await pedir(env, "GET", "/salud")).json();
  assert.equal(s.ok, true);
  assert.ok(s.edadS >= 0);
  const p = await pedir(env, "GET", "/");
  assert.match(p.headers.get("content-type"), /text\/html/);
  assert.match(await p.text(), /Estado de Red TeleCorp/);
});

test("utilidades", () => {
  assert.ok(mismoToken("abc", "abc"));
  assert.ok(!mismoToken("abd", "abc"));
  assert.ok(!mismoToken("ab", "abc"));
  assert.ok(!mismoToken("abc", ""));
  assert.equal(validarPublicacion(publicacion()), null);
  const e = estadoDe({ publicadoEn: "2026-11-15T20:00:00Z", estados: { GLOBAL: estado() } }, "GLOBAL", Date.parse("2026-11-15T20:05:00Z"));
  assert.equal(e.respaldo.edadS, 300);
});
