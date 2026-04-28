import SpaceGame from "./components/SpaceGame";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-[#0a0a1a] p-4">
      <SpaceGame />
      <div className="mt-6 text-center">
        <h2 className="text-gray-400 text-sm">操作说明</h2>
        <div className="flex gap-8 mt-2 text-gray-500 text-xs">
          <span>⬆️⬇️⬅️➡️ / WASD - 移动</span>
          <span>空格 - 射击</span>
        </div>
      </div>
    </div>
  );
}
