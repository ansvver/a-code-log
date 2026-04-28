# CODEBUDDY.md

This file provides guidance to CodeBuddy Code when working with code in this repository.

## Development Commands

- **Setup**: `npm run setup` - Installs dependencies, generates Prisma client, and runs migrations.
- **Development**: `npm run dev` - Starts the Next.js development server with Turbopack.
- **Build**: `npm run build` - Builds the application for production.
- **Testing**:
  - Run all tests: `npm run test`
  - Run a specific test: `npx vitest path/to/test.test.tsx`
- **Linting**: `npm run lint`
- **Database**:
  - Reset database: `npm run db:reset`
  - Prisma Studio: `npx prisma studio`

## High-Level Architecture

UIGen is an AI-powered React component generator that utilizes a virtual file system to enable live previews without writing files to the local disk.

### 1. Virtual File System (VFS)
- **Core Logic**: `src/lib/file-system.ts` defines the `VirtualFileSystem` class, which manages an in-memory tree of files and directories.
- **State Management**: `src/lib/contexts/file-system-context.tsx` provides the VFS state to the frontend components.
- **AI Tools**: The AI (Claude) interacts with the VFS via tools defined in `src/lib/tools/str-replace.ts` and `src/lib/tools/file-manager.ts`. These tools translate AI commands (like `create`, `str_replace`, `delete`) into VFS operations.

### 2. AI Integration
- **API Route**: `src/app/api/chat/route.ts` handles the AI chat stream using the Vercel AI SDK.
- **System Prompt**: `src/lib/prompts/generation.tsx` contains the instructions for the AI on how to structure components (e.g., using `@/` for imports, requiring `/App.jsx` as an entry point).
- **Tool Calling**: The server-side API provides tools to the model, which are then mirrored in the frontend via `handleToolCall` in the `FileSystemProvider`.

### 3. Live Preview & Transformation
- **Transformation**: `src/lib/transform/jsx-transformer.ts` uses `@babel/standalone` to transform JSX/TSX code in the VFS into browser-executable JavaScript.
- **Sandbox**: `src/components/preview/PreviewFrame.tsx` creates an iframe sandbox. It generates a `Blob` URL for each file and uses an `importmap` to resolve local and third-party dependencies (via `esm.sh`).
- **Entry Point**: The system looks for `/App.jsx` or `/App.tsx` as the primary entry point to render the component tree.

### 4. Persistence & Data Model
- **Schema**: `prisma/schema.prisma` defines `User` and `Project` models.
- **Project Data**: A `Project` record stores the entire chat history (`messages`) and the serialized state of the VFS (`data`) as JSON strings.
- **Server Actions**: `src/actions/` contains logic for fetching and managing projects from the SQLite database.

## CodeBuddy Added Memories
- Use comments sparingly. Only comment complex code.
- The database schema is defined in the @prisma/schema.prisma file. Reference it anytime you need to understand the structure of data stored in the database.
