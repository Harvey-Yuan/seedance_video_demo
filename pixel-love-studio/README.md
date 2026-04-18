# Dating Story Studio 💌

A cute, pixel-art inspired frontend demo that turns real dating stories into AI-generated short drama video pipelines. Built for hackathon vibes — pastel pink, lavender, and a sprinkle of sparkles ✨

> Frontend-only demo. All outputs are mocked — no backend, no API keys, no auth.

## ✨ Features

- **Landing page** — paste your dating story (or use the sample)
- **Workflow page** — 4 adorable pixel characters guide you through the pipeline:
  1. 🎬 **Director** — Story → Structure
  2. 🎨 **Visual** — Character / Scene / Style
  3. 📝 **Prompt** — Prompt Assembly
  4. 💃 **Seedance** — Final Video Output

## 🛠 Tech Stack

- **React 18** + **TypeScript**
- **Vite 5** (dev server + build)
- **Tailwind CSS v3** with a custom pastel pixel design system
- **shadcn/ui** components
- **React Router** for navigation

## 🚀 Run Locally

### Prerequisites

You need **Node.js 18+** installed. We recommend using [nvm](https://github.com/nvm-sh/nvm) to manage versions.

This project uses **Bun** as the package manager (a `bun.lock` is committed), but `npm` and `pnpm` work too.

### 1. Clone the repo

```bash
git clone <YOUR_GIT_URL>
cd <YOUR_PROJECT_NAME>
```

### 2. Install dependencies

Pick whichever package manager you have installed:

```bash
# with bun (recommended — matches the lockfile)
bun install

# or with npm
npm install

# or with pnpm
pnpm install
```

### 3. Start the dev server

```bash
bun run dev
# or: npm run dev
```

The app will be available at **http://localhost:8080**

The dev server supports hot reload — edit any file in `src/` and the browser will update instantly.

### 4. Build for production

```bash
bun run build
# or: npm run build
```

The optimized output will be in the `dist/` folder. To preview the production build locally:

```bash
bun run preview
# or: npm run preview
```

## 📁 Project Structure

```
src/
├── assets/              # Pixel character art (PNG)
├── components/
│   ├── panels/          # Director / Visual / Prompt / Seedance output panels
│   ├── ui/              # shadcn/ui primitives
│   ├── Sidebar.tsx
│   ├── WorkflowStrip.tsx
│   └── PixelDecor.tsx
├── lib/
│   └── mockData.ts      # Sample story + all mocked AI outputs
├── pages/
│   ├── Landing.tsx      # Story input page
│   ├── Workflow.tsx     # Main pipeline page
│   └── NotFound.tsx
├── index.css            # Design tokens (HSL colors, pixel shadows, animations)
└── main.tsx
```

## 🎨 Design System

All colors live as HSL tokens in `src/index.css` and are exposed as Tailwind classes via `tailwind.config.ts`. Don't hardcode colors in components — use semantic tokens like `bg-primary`, `text-foreground`, `shadow-pixel`.

## 📝 Notes

- No `.env` file is needed — there are no API calls.
- All "AI outputs" come from `src/lib/mockData.ts`. Edit that file to change the demo content.
- Default port is **8080** (configured in `vite.config.ts`).

Happy hacking 💖
