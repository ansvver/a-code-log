# Space Game

An arcade-style space shooter built with [Next.js](https://nextjs.org) + Canvas.

## Getting Started

### Prerequisites

- Node.js + npm (see `package.json` engines if you add them later)

### Start dev server (port 3005)

Recommended (starts in background and writes logs):

```bash
./scripts/dev-3005.sh
```

Open http://127.0.0.1:3005

You can override defaults via env vars:

```bash
PORT=3005 HOST=127.0.0.1 LOG_FILE=.dev-3005.log ./scripts/dev-3005.sh
```

Manual start (foreground):

```bash
npm run dev -- -H 127.0.0.1 -p 3005
```

### Stop dev server

- Find the PID: `lsof -nP -iTCP:3005 -sTCP:LISTEN`
- Stop it: `kill <PID>`
- View logs: `tail -f .dev-3005.log`

### Edit code

- Main page: `src/app/page.tsx`
- Game component: `src/app/components/SpaceGame.tsx`

## Gameplay

- Move: `WASD` or arrow keys
- Shoot: `Space`
- Restart: `Enter` (on game over)

## Data / Persistence

- **High score** is persisted in `localStorage` under key `spaceGameHighScore`.
- **Leaderboard (Top 10)** is persisted in `localStorage` under key `spaceGameLeaderboard` (name + score + timestamp).

## Production

```bash
npm run build
npm run start -- -p 3005
```

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
