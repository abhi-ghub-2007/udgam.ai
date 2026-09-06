/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Overrides the API base URL at build time. Optional: falls back to the
      runtime global, then to the local dev backend. */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
