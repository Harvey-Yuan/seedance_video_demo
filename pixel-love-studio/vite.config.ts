import type { Connect } from "vite";
import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

/** Dev + `vite preview` must both proxy `/api` → Seedance backend, or fetch hits the static server and returns 404. */
const apiProxy = {
  "/api": {
    target: "http://127.0.0.1:8000",
    changeOrigin: true,
  },
};

/** Serve static deck at http://localhost:8080/slides (public/slides/index.html). */
function slidesPublicRoute(): Plugin {
  const rewrite: Connect.NextHandleFunction = (req, _res, next) => {
    const raw = req.url ?? "";
    const pathOnly = raw.split("?")[0];
    if (pathOnly === "/slides" || pathOnly === "/slides/") {
      const q = raw.includes("?") ? "?" + raw.split("?").slice(1).join("?") : "";
      req.url = "/slides/index.html" + q;
    }
    next();
  };
  return {
    name: "slides-public-route",
    configureServer(server) {
      server.middlewares.use(rewrite);
    },
    configurePreviewServer(server) {
      server.middlewares.use(rewrite);
    },
  };
}

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => ({
  server: {
    host: "::",
    port: 8080,
    hmr: {
      overlay: false,
    },
    proxy: apiProxy,
  },
  preview: {
    port: 8080,
    proxy: apiProxy,
  },
  plugins: [slidesPublicRoute(), react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime", "@tanstack/react-query", "@tanstack/query-core"],
  },
}));
