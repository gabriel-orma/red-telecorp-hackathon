// Autenticación con Cognito (D9) usando su API JSON directamente (sin SDK).
// Los tokens se guardan en localStorage como comodidad local; la validación real la hace el autorizador JWT del API.
import { useEffect, useState } from "react";
import { fetchApi } from "./limitador";

interface Config { region: string; userPoolId: string; clientId: string }
export interface Perfil {
  email: string; nombre: string; dni: string; numeroServicio: string; telefono?: string; zonaId: string; avisosEmail: "0" | "1";
}
interface Sesion { idToken: string; refreshToken: string; expira: number }

const CLAVE = "telecorp.sesion";
let config: Promise<Config> | null = null;
const oyentes = new Set<() => void>();
/** true cuando la sesión se perdió porque Cognito rechazó las credenciales (no por cerrar sesión): se muestra un aviso. */
let caducada = false;

/** Error de Cognito con su tipo (distingue una credencial rechazada de un fallo pasajero). */
class ErrorCognito extends Error {
  constructor(mensaje: string, readonly tipo: string) { super(mensaje); }
}

function obtenerConfig(): Promise<Config> {
  config ??= fetchApi("/api/config").then((r) => r.json());
  return config;
}

async function cognito<T>(accion: string, cuerpo: object): Promise<T> {
  const { region } = await obtenerConfig();
  const r = await fetch(`https://cognito-idp.${region}.amazonaws.com/`, {
    method: "POST",
    headers: { "content-type": "application/x-amz-json-1.1", "x-amz-target": `AWSCognitoIdentityProviderService.${accion}` },
    body: JSON.stringify(cuerpo),
  });
  const datos = await r.json().catch(() => ({}));
  if (!r.ok) throw new ErrorCognito(traducirError(datos.__type, datos.message), String(datos.__type ?? ""));
  return datos as T;
}

function traducirError(tipo = "", mensaje = ""): string {
  if (tipo.includes("UsernameExists")) return "Ya existe una cuenta con ese correo.";
  if (tipo.includes("NotAuthorized")) return "Correo o contraseña incorrectos.";
  if (tipo.includes("InvalidPassword")) return "La contraseña debe tener al menos 8 caracteres, con minúsculas y números.";
  if (tipo.includes("UserLambdaValidation")) return mensaje.replace(/^PreSignUp failed with error /, "").replace(/\.$/, "") + ".";
  if (tipo.includes("InvalidParameter")) return "Revisa los datos: " + mensaje;
  return mensaje || "No se pudo completar la operación.";
}

function leer(): Sesion | null {
  try { return JSON.parse(localStorage.getItem(CLAVE) ?? "null"); } catch { return null; }
}
function guardar(s: Sesion | null) {
  if (s) caducada = false;   // volver a ingresar limpia el aviso
  try { s ? localStorage.setItem(CLAVE, JSON.stringify(s)) : localStorage.removeItem(CLAVE); } catch { /* sin almacenamiento */ }
  oyentes.forEach((f) => f());
}

export function decodificar(token: string): Record<string, string> {
  const base = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(decodeURIComponent(escape(atob(base))));
}

export function perfilDe(token: string): Perfil {
  const c = decodificar(token);
  return {
    email: c.email, nombre: c.name, dni: c["custom:dni"], numeroServicio: c["custom:numeroServicio"],
    telefono: c.phone_number, zonaId: c["custom:zonaId"], avisosEmail: (c["custom:avisosEmail"] as "0" | "1") ?? "0",
  };
}

export async function registrar(datos: Perfil & { password: string }) {
  const { clientId } = await obtenerConfig();
  const atributos: Record<string, string | undefined> = {
    email: datos.email, name: datos.nombre, phone_number: datos.telefono || undefined,
    "custom:dni": datos.dni, "custom:numeroServicio": datos.numeroServicio,
    "custom:zonaId": datos.zonaId, "custom:avisosEmail": datos.avisosEmail,
  };
  await cognito("SignUp", {
    ClientId: clientId, Username: datos.email, Password: datos.password,
    UserAttributes: Object.entries(atributos).filter(([, v]) => v).map(([Name, Value]) => ({ Name, Value })),
  });
  await iniciarSesion(datos.email, datos.password); // la cuenta se auto-confirma (trigger PreSignUp)
}

export async function iniciarSesion(email: string, password: string) {
  const { clientId } = await obtenerConfig();
  const r = await cognito<{ AuthenticationResult: { IdToken: string; RefreshToken: string; ExpiresIn: number } }>("InitiateAuth", {
    ClientId: clientId, AuthFlow: "USER_PASSWORD_AUTH", AuthParameters: { USERNAME: email, PASSWORD: password },
  });
  const a = r.AuthenticationResult;
  guardar({ idToken: a.IdToken, refreshToken: a.RefreshToken, expira: Date.now() + (a.ExpiresIn - 60) * 1000 });
}

export function cerrarSesion() { guardar(null); }

/** La sesión dejó de ser válida (refresh token vencido o ID token rechazado por el API): se cierra y se avisa en pantalla. */
export function caducarSesion() {
  const habia = leer() !== null;
  guardar(null);
  if (habia) { caducada = true; oyentes.forEach((f) => f()); }
}

export function descartarAvisoSesion() { caducada = false; oyentes.forEach((f) => f()); }

/** ¿Hay que avisar que la sesión caducó? */
export function useSesionCaducada(): boolean {
  const [v, setV] = useState(caducada);
  useEffect(() => {
    const f = () => setV(caducada);
    oyentes.add(f);
    return () => { oyentes.delete(f); };
  }, []);
  return v;
}

/** ID token vigente (renueva con el refresh token si expiró). null si no hay sesión. */
export async function tokenVigente(): Promise<string | null> {
  const s = leer();
  if (!s) return null;
  if (Date.now() < s.expira) return s.idToken;
  try {
    const { clientId } = await obtenerConfig();
    const r = await cognito<{ AuthenticationResult: { IdToken: string; ExpiresIn: number } }>("InitiateAuth", {
      ClientId: clientId, AuthFlow: "REFRESH_TOKEN_AUTH", AuthParameters: { REFRESH_TOKEN: s.refreshToken },
    });
    const nueva = { ...s, idToken: r.AuthenticationResult.IdToken, expira: Date.now() + (r.AuthenticationResult.ExpiresIn - 60) * 1000 };
    guardar(nueva);
    return nueva.idToken;
  } catch (e) {
    // Solo una credencial rechazada (refresh token vencido o revocado) cierra la sesión, y se avisa. Un fallo de red o un error
    // pasajero de Cognito conserva la sesión: se reintenta en la siguiente llamada en lugar de sacar al operador.
    if (e instanceof ErrorCognito && /NotAuthorized|UserNotFound/.test(e.tipo)) { caducarSesion(); return null; }
    return s.idToken;
  }
}

/** ¿El ID token pertenece al grupo `operadores`? Solo decide qué mostrar: la autorización real la hace el API. */
export function esOperadorToken(token: string): boolean {
  const grupos = (decodificar(token) as Record<string, unknown>)["cognito:groups"];
  return Array.isArray(grupos) && grupos.includes("operadores");
}

/** true si hay sesión y es de un operador (se actualiza al iniciar o cerrar sesión). */
export function useEsOperador(): boolean {
  const calcular = () => { const s = leer(); try { return s ? esOperadorToken(s.idToken) : false; } catch { return false; } };
  const [esOperador, setEsOperador] = useState<boolean>(calcular);
  useEffect(() => {
    const f = () => setEsOperador(calcular());
    oyentes.add(f);
    return () => { oyentes.delete(f); };
  }, []);
  return esOperador;
}

/** Perfil de la sesión actual (se actualiza al iniciar o cerrar sesión). */
export function usePerfil(): Perfil | null {
  const calcular = () => { const s = leer(); try { return s ? perfilDe(s.idToken) : null; } catch { return null; } };
  const [perfil, setPerfil] = useState<Perfil | null>(calcular);
  useEffect(() => {
    const f = () => setPerfil(calcular());
    oyentes.add(f);
    return () => { oyentes.delete(f); };
  }, []);
  return perfil;
}
