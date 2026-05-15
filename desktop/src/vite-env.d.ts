/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Empty string = same-origin API (hosted Docker / Azure). Undefined = use dev proxy or desktop default. */
  readonly VITE_API_BASE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
