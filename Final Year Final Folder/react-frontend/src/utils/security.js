// Simple SHA-256 hashing helper that relies on the Web Crypto API
export const hashPassword = async (password) => {
  if (typeof password !== "string") {
    throw new Error("Password must be a string");
  }

  if (!window?.crypto?.subtle) {
    throw new Error("Secure hashing is not supported in this environment");
  }

  const encoder = new TextEncoder();
  const data = encoder.encode(password);
  const hashBuffer = await window.crypto.subtle.digest("SHA-256", data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((byte) => byte.toString(16).padStart(2, "0")).join("");
};
