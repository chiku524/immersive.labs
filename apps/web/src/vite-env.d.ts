/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_STUDIO_API_URL?: string;
  /** If set, /p/plugins/* requires this passphrase (sessionStorage). */
  readonly VITE_PRIVATE_PLUGIN_DL_PASSWORD?: string;
  /**
   * If set, Fab plugin download links use this HTTPS URL prefix + zip filename (e.g. GitHub
   * Release `.../download/v1.0.0/`). If unset, links are same-origin `/plugin-packages/...`.
   */
  readonly VITE_FAB_MARKETPLACE_ZIP_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
