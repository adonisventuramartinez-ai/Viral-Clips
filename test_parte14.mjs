// Parte 14: cuentas, sesiones, foto de perfil. Corre las rutas /api y el middleware REALES contra una base de datos simulada.
// Ejecuta (Node 22.6 o más nuevo):  node --experimental-strip-types test_parte14.mjs
import { register } from "node:module";
import { fileURLToPath, pathToFileURL } from "node:url";
import assert from "node:assert/strict";

const ROOT = fileURLToPath(new URL(".", import.meta.url)).replace(/\/$/, "");
process.env.APP_PASSWORD = "clave-de-acceso";
process.env.SUPABASE_URL = "http://fake.supabase.local";
process.env.SUPABASE_SERVICE_ROLE_KEY = "fake-service-role";
process.env.NODE_ENV = "test";

// ---- módulos simulados: next/server, supabase y el alias "@/"
const NEXT_STUB = `
class Jar { constructor(){ this.items = {}; } set(n, v, o){ this.items[n] = { value: v, opts: o }; } }
export class NextResponse {
  constructor(body, init = {}) { this.body = body; this.status = init.status ?? 200; this.headers = init.headers ?? {}; this.cookies = new Jar(); }
  static json(body, init = {}) { return new NextResponse(body, init); }
  static next() { const r = new NextResponse(null); r.kind = "next"; return r; }
  static redirect(u) { const r = new NextResponse(null, { status: 307 }); r.kind = "redirect"; r.to = u.pathname; return r; }
}
export class NextRequest {}
`;
const SUPA_STUB = `export function createClient() { return globalThis.__fakeDb; }`;
const hooks = `
export async function resolve(spec, ctx, next) {
  if (spec === "next/server") return { url: "stub:next", shortCircuit: true };
  if (spec === "@supabase/supabase-js") return { url: "stub:supa", shortCircuit: true };
  if (spec.startsWith("@/")) return next(${JSON.stringify(pathToFileURL(ROOT).href)} + "/" + spec.slice(2) + ".ts", ctx);
  return next(spec, ctx);
}
export async function load(url, ctx, next) {
  if (url === "stub:next") return { format: "module", source: ${JSON.stringify(NEXT_STUB)}, shortCircuit: true };
  if (url === "stub:supa") return { format: "module", source: ${JSON.stringify(SUPA_STUB)}, shortCircuit: true };
  return next(url, ctx);
}`;
register("data:text/javascript," + encodeURIComponent(hooks));

// ---- base de datos simulada (solo la tabla accounts)
const rows = [];
let tableMissing = false;
const copy = (r) => ({ ...r });
globalThis.__fakeDb = {
  from(table) {
    assert.equal(table, "accounts");
    const q = { op: "select", filters: [], patch: null, row: null, returning: false, cols: null };
    const pick = (r) => (q.cols ? Object.fromEntries(q.cols.map((c) => [c, r[c]])) : copy(r));   // como Supabase: solo las columnas pedidas
    const run = () => {
      if (tableMissing) return { data: null, error: { message: 'relation "public.accounts" does not exist' } };
      if (q.op === "insert") {
        if (rows.some((r) => r.username === q.row.username)) return { data: null, error: { code: "23505", message: "duplicate key value" } };
        rows.push({ avatar: null, last_login: null, ...q.row }); return { data: null, error: null };
      }
      const match = rows.filter((r) => q.filters.every(([k, v]) => r[k] === v));
      if (q.op === "update") { match.forEach((r) => Object.assign(r, q.patch)); return { data: q.returning ? match.map(pick) : null, error: null }; }
      return { data: match.map(pick), count: rows.length, error: null };
    };
    const b = {
      select(c) { if (q.op === "update") q.returning = true; q.cols = String(c || "").split(",").map((x) => x.trim()).filter(Boolean); return b; },
      insert(r) { q.op = "insert"; q.row = r; return b; },
      update(p) { q.op = "update"; q.patch = p; return b; },
      eq(k, v) { q.filters.push([k, v]); return b; },
      maybeSingle() { const r = run(); return Promise.resolve({ data: Array.isArray(r.data) ? (r.data[0] ?? null) : r.data, error: r.error }); },
      then(res, rej) { return Promise.resolve(run()).then(res, rej); },
    };
    return b;
  },
};

const { authToken, signSession, verifySession, sessionSecret } = await import("./lib/auth.ts");
const { hashPassword, checkPassword } = await import("./lib/password.ts");
const P = await import("./lib/profile.ts");
const RL = await import("./lib/ratelimit.ts");
const login = await import("./app/api/login/route.ts");
const registro = await import("./app/api/registro/route.ts");
const cuenta = await import("./app/api/cuenta/route.ts");
const logout = await import("./app/api/logout/route.ts");
const { middleware } = await import("./middleware.ts");

let ok = 0;
const check = (name, cond) => { assert.ok(cond, name); ok++; };
let ipN = 0;
const newIp = () => `10.0.0.${++ipN}`;
const req = (path, method, body, { ip, cookie } = {}) =>
  new Request("http://app.local" + path, { method, headers: { "content-type": "application/json", "x-forwarded-for": ip || newIp(), ...(cookie ? { cookie } : {}) }, body: body === undefined ? undefined : JSON.stringify(body) });
const sessionOf = (res) => res.cookies.items.cf_session?.value;
const cookieHdr = (res) => `cf_session=${sessionOf(res)}`;

// ---------------------------------------------------------------- contraseñas
const h1 = await hashPassword("secreta123"), h2 = await hashPassword("secreta123");
check("la contraseña se guarda con scrypt y sal (no en claro)", h1.startsWith("scrypt$") && !h1.includes("secreta123"));
check("dos hashes de la misma contraseña son distintos (sal propia)", h1 !== h2);
check("contraseña buena entra", await checkPassword("secreta123", h1));
check("contraseña mala no entra", !(await checkPassword("secreta124", h1)));
check("sin hash guardado nunca entra", !(await checkPassword("", null)) && !(await checkPassword("x", undefined)));
check("hash dañado no entra ni rompe", !(await checkPassword("x", "basura")) && !(await checkPassword("x", "md5$a$b")));

// ---------------------------------------------------------------- sesiones firmadas
const tok = await signSession("juan.p", "k");
check("sesión válida devuelve el usuario", (await verifySession(tok, "k")) === "juan.p");
check("otra clave de firma: no vale", (await verifySession(tok, "otra")) === null);
check("cambiar el usuario en la cookie: no vale", (await verifySession(tok.replace("juan.p", "admin1"), "k")) === null);
check("sesión vencida: no vale", (await verifySession(await signSession("juan.p", "k", 30, Date.now() - 31 * 86400e3), "k")) === null);
check("basura: no vale", (await verifySession("x", "k")) === null && (await verifySession("a-b-c", "k")) === null && (await verifySession("", "k")) === null && (await verifySession(undefined, "k")) === null);

// ---------------------------------------------------------------- validadores de perfil
check("usuario se limpia (minúsculas, sin @)", P.cleanUsername("  @JuanP ") === "juanp");
check("usuario con espacios, tildes o muy corto: no", P.cleanUsername("ju an") === null && P.cleanUsername("juán") === null && P.cleanUsername("ab") === null && P.cleanUsername("a".repeat(25)) === null && P.cleanUsername(5) === null);
check("nombre limpia espacios y símbolos peligrosos", P.cleanName("  Juan   <b>Pérez</b> ") === "Juan b Pérez /b");
check("nombre muy corto o largo: no", P.cleanName("J") === null && P.cleanName("x".repeat(41)) === null && P.cleanName(null) === null);
check("contraseña de 8 sí, de 7 no", P.validPassword("12345678") && !P.validPassword("1234567") && !P.validPassword("x".repeat(101)));
check("foto: jpeg/png/webp sí; svg, html o texto no", P.validAvatar("data:image/jpeg;base64,AAAA") && P.validAvatar("data:image/png;base64,AAAA") && !P.validAvatar("data:image/svg+xml;base64,AAAA") && !P.validAvatar("javascript:alert(1)") && !P.validAvatar("data:image/png;base64,AA\"onerror=\"x"));
check("foto demasiado grande: no", !P.validAvatar("data:image/jpeg;base64," + "A".repeat(P.AVATAR_MAX)));
check("iniciales", P.initials("Juan Pérez") === "JP" && P.initials("juan") === "JU" && P.initials("  ") === "?");

// ---------------------------------------------------------------- límite de intentos
RL.addFail("t1"); RL.addFail("t1"); RL.addFail("t1"); RL.addFail("t1");
check("4 fallos: todavía puede", RL.blockedFor("t1") === 0);
RL.addFail("t1");
check("5 fallos: bloqueado", RL.blockedFor("t1") > 0);
check("otra clave no se afecta", RL.blockedFor("t2") === 0);
check("pasada la ventana se libera", RL.blockedFor("t1", Date.now() + 16 * 60 * 1000) === 0);
RL.clearFails("t1");
check("un acceso correcto borra los fallos", RL.blockedFor("t1") === 0);

// ---------------------------------------------------------------- registro
const good = { username: "JuanP", display_name: "Juan  Pérez", password: "secreta123", code: "clave-de-acceso" };
let r = await registro.POST(req("/api/registro", "POST", { ...good, code: "mal" }));
check("código de acceso malo: 401 y no crea nada", r.status === 401 && rows.length === 0);
r = await registro.POST(req("/api/registro", "POST", { ...good, username: "j u" }));
check("usuario inválido: 400", r.status === 400 && rows.length === 0);
r = await registro.POST(req("/api/registro", "POST", { ...good, password: "corta" }));
check("contraseña corta: 400", r.status === 400 && rows.length === 0);
r = await registro.POST(req("/api/registro", "POST", { ...good, display_name: "J" }));
check("nombre corto: 400", r.status === 400 && rows.length === 0);
r = await registro.POST(req("/api/registro", "POST", good));
check("registro bueno: 200 y ya entra con cookie firmada", r.status === 200 && (await verifySession(sessionOf(r), sessionSecret())) === "juanp");
check("la cookie es httpOnly y dura 30 días", r.cookies.items.cf_session.opts.httpOnly === true && r.cookies.items.cf_session.opts.maxAge === 2592000);
check("se guardó limpio y con hash", rows.length === 1 && rows[0].username === "juanp" && rows[0].display_name === "Juan Pérez" && rows[0].password_hash.startsWith("scrypt$"));
r = await registro.POST(req("/api/registro", "POST", good));
check("usuario repetido: 409", r.status === 409 && rows.length === 1);
const ipR = newIp();
for (let i = 0; i < 5; i++) await registro.POST(req("/api/registro", "POST", { ...good, code: "mal" }, { ip: ipR }));
r = await registro.POST(req("/api/registro", "POST", good, { ip: ipR }));
check("5 códigos malos seguidos: esa IP queda bloqueada (429), aunque ahora acierte", r.status === 429);
tableMissing = true;
r = await registro.POST(req("/api/registro", "POST", { ...good, username: "otro1" }));
check("sin la migración 0016 lo dice claro", r.status === 500 && /0016_cuentas/.test(r.body.error));
tableMissing = false;

// ---------------------------------------------------------------- login
r = await login.POST(req("/api/login", "POST", { username: "@JUANP", password: "secreta123" }));
check("login con cuenta: 200 y cookie cf_session", r.status === 200 && (await verifySession(sessionOf(r), sessionSecret())) === "juanp" && r.body.user.display_name === "Juan Pérez");
check("el login no devuelve ni el hash ni la foto", !JSON.stringify(r.body).includes("scrypt") && !("avatar" in r.body.user));
check("login actualiza last_login", !!rows[0].last_login);
const bad1 = await login.POST(req("/api/login", "POST", { username: "juanp", password: "equivocada" }));
const bad2 = await login.POST(req("/api/login", "POST", { username: "nadie", password: "secreta123" }));
check("contraseña mala y usuario inexistente dan el mismo mensaje (401)", bad1.status === 401 && bad2.status === 401 && bad1.body.error === bad2.body.error);
r = await login.POST(req("/api/login", "POST", { password: "clave-de-acceso" }));
check("solo la clave de acceso: entra como antes (cf_auth)", r.status === 200 && r.cookies.items.cf_auth.value === (await authToken("clave-de-acceso")) && !r.cookies.items.cf_session);
r = await login.POST(req("/api/login", "POST", { password: "no" }));
check("clave de acceso mala: 401", r.status === 401);
const ipL = newIp();
for (let i = 0; i < 5; i++) await login.POST(req("/api/login", "POST", { username: "juanp", password: "x" }, { ip: ipL }));
r = await login.POST(req("/api/login", "POST", { username: "juanp", password: "secreta123" }, { ip: ipL }));
check("5 fallos seguidos: bloquea esa IP (429)", r.status === 429);
check("registro y login cuentan aparte", RL.blockedFor(`reg:${ipL}`) === 0);
tableMissing = true;
r = await login.POST(req("/api/login", "POST", { username: "juanp", password: "x" }));
check("login sin la migración 0016 lo dice claro", r.status === 500 && /0016_cuentas/.test(r.body.error));
tableMissing = false;

// ---------------------------------------------------------------- mi cuenta
const lg = await login.POST(req("/api/login", "POST", { username: "juanp", password: "secreta123" }));
const ck = cookieHdr(lg);
r = await cuenta.GET(req("/api/cuenta", "GET"));
check("sin sesión de cuenta: user null", r.body.user === null);
r = await cuenta.GET(req("/api/cuenta", "GET", undefined, { cookie: "cf_session=juanp-9999999999-" + "0".repeat(64) }));
check("cookie falsificada: user null", r.body.user === null);
r = await cuenta.GET(req("/api/cuenta", "GET", undefined, { cookie: ck }));
check("con sesión: devuelve usuario, nombre y foto", r.body.user.username === "juanp" && r.body.user.display_name === "Juan Pérez" && r.body.user.avatar === null);
check("mi cuenta nunca devuelve el hash", !("password_hash" in r.body.user));
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { display_name: "Hack" }));
check("cambiar perfil sin sesión: 401", r.status === 401 && rows[0].display_name === "Juan Pérez");
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { display_name: "  Juan P. " }, { cookie: ck }));
check("cambiar nombre", r.status === 200 && r.body.user.display_name === "Juan P." && rows[0].display_name === "Juan P.");
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { display_name: "J" }, { cookie: ck }));
check("nombre inválido: 400 y no cambia", r.status === 400 && rows[0].display_name === "Juan P.");
const foto = "data:image/jpeg;base64," + "A".repeat(2000);
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { avatar: foto }, { cookie: ck }));
check("subir foto", r.status === 200 && rows[0].avatar === foto);
r = await cuenta.GET(req("/api/cuenta", "GET", undefined, { cookie: ck }));
check("la foto se ve al abrir la app", r.body.user.avatar === foto);
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { avatar: "data:image/svg+xml;base64,AAAA" }, { cookie: ck }));
check("foto svg: 400 y no cambia", r.status === 400 && rows[0].avatar === foto);
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { avatar: "data:image/jpeg;base64," + "A".repeat(P.AVATAR_MAX) }, { cookie: ck }));
check("foto enorme: 400", r.status === 400 && rows[0].avatar === foto);
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { avatar: null }, { cookie: ck }));
check("quitar foto", r.status === 200 && rows[0].avatar === null);
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", {}, { cookie: ck }));
check("sin cambios: 400", r.status === 400);
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { current_password: "mala", new_password: "nuevaclave1" }, { cookie: ck }));
check("cambiar contraseña con la actual mala: 401", r.status === 401 && (await checkPassword("secreta123", rows[0].password_hash)));
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { current_password: "secreta123", new_password: "corta" }, { cookie: ck }));
check("contraseña nueva corta: 400", r.status === 400);
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { current_password: "secreta123", new_password: "nuevaclave1" }, { cookie: ck }));
check("cambiar contraseña", r.status === 200 && (await checkPassword("nuevaclave1", rows[0].password_hash)) && !(await checkPassword("secreta123", rows[0].password_hash)));
check("el cambio de contraseña no se cuela en la respuesta", !JSON.stringify(r.body).includes("scrypt"));
r = await login.POST(req("/api/login", "POST", { username: "juanp", password: "nuevaclave1" }));
check("entra con la contraseña nueva", r.status === 200);
// 5 intentos malos de contraseña actual bloquean el cambio
for (let i = 0; i < 5; i++) await cuenta.PATCH(req("/api/cuenta", "PATCH", { current_password: "mala", new_password: "otraclave12" }, { cookie: ck }));
r = await cuenta.PATCH(req("/api/cuenta", "PATCH", { current_password: "nuevaclave1", new_password: "otraclave12" }, { cookie: ck }));
check("5 contraseñas actuales malas bloquean el cambio (429)", r.status === 429);

// ---------------------------------------------------------------- salir
r = await logout.POST();
check("salir borra las dos cookies", r.cookies.items.cf_session.opts.maxAge === 0 && r.cookies.items.cf_auth.opts.maxAge === 0 && r.cookies.items.cf_session.value === "");

// ---------------------------------------------------------------- middleware real
const mw = async (pathname, cookies = {}) => middleware({ nextUrl: { pathname, clone: () => ({ pathname }) }, cookies: { get: (n) => (cookies[n] ? { value: cookies[n] } : undefined) } });
const sess = await signSession("juanp", "clave-de-acceso");
check("sin cookie: manda a /login", (await mw("/crear")).kind === "redirect" && (await mw("/crear")).to === "/login");
check("sin cookie en /api: 401", (await mw("/api/clips")).status === 401);
for (const p of ["/login", "/api/login", "/api/registro", "/api/logout"]) check(`${p} abierto`, (await mw(p)).kind === "next");
check("/api/cuenta pide sesión", (await mw("/api/cuenta")).status === 401);
check("con sesión de cuenta: pasa", (await mw("/crear", { cf_session: sess })).kind === "next" && (await mw("/api/clips", { cf_session: sess })).kind === "next");
check("con la cookie vieja (solo clave): pasa", (await mw("/crear", { cf_auth: await authToken("clave-de-acceso") })).kind === "next");
check("sesión firmada con otra clave: no pasa", (await mw("/crear", { cf_session: await signSession("juanp", "otra") })).kind === "redirect");
check("sesión manipulada: no pasa", (await mw("/crear", { cf_session: sess.replace("juanp", "admin1") })).kind === "redirect");
check("sesión vencida: no pasa", (await mw("/crear", { cf_session: await signSession("juanp", "clave-de-acceso", 30, Date.now() - 40 * 86400e3) })).kind === "redirect");
check("cambiar APP_PASSWORD cierra todas las sesiones", await (async () => { process.env.APP_PASSWORD = "otra-clave"; const x = await mw("/crear", { cf_session: sess }); process.env.APP_PASSWORD = "clave-de-acceso"; return x.kind === "redirect"; })());

console.log(`OK: ${ok} comprobaciones de la Parte 14`);
