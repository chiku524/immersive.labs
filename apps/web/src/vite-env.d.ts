/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_STUDIO_API_URL?: string;
  /** If set, /p/plugins/* requires this passphrase (sessionStorage). */
  readonly VITE_PRIVATE_PLUGIN_DL_PASSWORD?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
