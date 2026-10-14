import { FlatCompat } from "@eslint/eslintrc";

const compat = new FlatCompat({ baseDirectory: import.meta.dirname });
const config = [
  { ignores: [".next/**", "node_modules/**", "coverage/**", "test-results/**", "playwright-report/**", "postcss.config.js"] },
  ...compat.extends("next/core-web-vitals")
];

export default config;
