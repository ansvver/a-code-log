"use client";

import { useEffect, useRef, useState, useCallback } from "react";

// 游戏常量
const CANVAS_WIDTH = 800;
const CANVAS_HEIGHT = 600;
const PLAYER_WIDTH = 60;
const PLAYER_HEIGHT = 70;
const BULLET_WIDTH = 4;
const BULLET_HEIGHT = 15;
const ENEMY_SIZE = 35;
const ASTEROID_SIZE = 40;
const PLAYER_SPEED = 8;
const BULLET_SPEED = 12;
const ENEMY_SPEED = 3;
const ASTEROID_SPEED = 2;
const LEADERBOARD_LIMIT = 10;

// 类型定义
interface GameObject {
  x: number;
  y: number;
  width: number;
  height: number;
}

interface LeaderboardEntry {
  id: string;
  name: string;
  score: number;
  createdAt: number;
}

interface Bullet extends GameObject {
  id: number;
}

interface Enemy extends GameObject {
  id: number;
  type: "enemy" | "asteroid";
  health: number;
}

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  color: string;
}

interface Star {
  x: number;
  y: number;
  size: number;
  speed: number;
}

export default function SpaceGame() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const highScoreRef = useRef(0);
  const [gameState, setGameState] = useState<"menu" | "playing" | "gameOver">("menu");
  const [score, setScore] = useState(0);
  const nameInputRef = useRef<HTMLInputElement>(null);

  const readHighScoreFromStorage = (): number => {
    if (typeof window === "undefined") return 0;
    try {
      const saved = localStorage.getItem("spaceGameHighScore");
      if (!saved) return 0;
      const parsed = Number(saved);
      return Number.isFinite(parsed) ? parsed : 0;
    } catch {
      return 0;
    }
  };

  const [highScore, setHighScore] = useState(readHighScoreFromStorage);
  const [isNewRecord, setIsNewRecord] = useState(false);

  const readLeaderboardFromStorage = (): LeaderboardEntry[] => {
    if (typeof window === "undefined") return [];
    try {
      const saved = localStorage.getItem("spaceGameLeaderboard");
      if (!saved) return [];
      const parsed = JSON.parse(saved) as unknown;
      if (!Array.isArray(parsed)) return [];
      return parsed
        .filter((entry) => {
          if (!entry || typeof entry !== "object") return false;
          const candidate = entry as Partial<LeaderboardEntry>;
          return (
            typeof candidate.id === "string" &&
            typeof candidate.name === "string" &&
            typeof candidate.score === "number" &&
            typeof candidate.createdAt === "number"
          );
        })
        .map((entry) => entry as LeaderboardEntry)
        .sort((a, b) => (b.score - a.score) || (a.createdAt - b.createdAt))
        .slice(0, LEADERBOARD_LIMIT);
    } catch {
      return [];
    }
  };

  const [leaderboard, setLeaderboard] = useState<LeaderboardEntry[]>(readLeaderboardFromStorage);
  const [playerName, setPlayerName] = useState("");
  const [hasSavedScore, setHasSavedScore] = useState(false);

  // 游戏状态 refs
  const playerRef = useRef({ x: CANVAS_WIDTH / 2 - PLAYER_WIDTH / 2, y: CANVAS_HEIGHT - 80 });
  const bulletsRef = useRef<Bullet[]>([]);
  const enemiesRef = useRef<Enemy[]>([]);
  const particlesRef = useRef<Particle[]>([]);
  const starsRef = useRef<Star[]>([]);
  const keysRef = useRef<Set<string>>(new Set());
  const bulletIdRef = useRef(0);
  const enemyIdRef = useRef(0);
  const frameRef = useRef(0);
  const animationRef = useRef<number | null>(null);
  const lastShotRef = useRef(0);
  const scoreRef = useRef(0);

  const saveHighScore = useCallback((nextHighScore: number) => {
    try {
      localStorage.setItem("spaceGameHighScore", String(nextHighScore));
    } catch (error) {
      console.error("Failed to save high score:", error);
    }
  }, []);

  const persistLeaderboard = useCallback((nextLeaderboard: LeaderboardEntry[]) => {
    try {
      localStorage.setItem("spaceGameLeaderboard", JSON.stringify(nextLeaderboard));
    } catch (error) {
      console.error("Failed to save leaderboard:", error);
    }
  }, []);

  useEffect(() => {
    highScoreRef.current = highScore;
  }, [highScore]);

  const updateHighScore = useCallback((finalScore: number) => {
    const prevHighScore = highScoreRef.current;
    const nextHighScore = Math.max(prevHighScore, finalScore);
    const didBreakRecord = finalScore > prevHighScore;

    setIsNewRecord(didBreakRecord);
    if (nextHighScore !== prevHighScore) {
      highScoreRef.current = nextHighScore;
      setHighScore(nextHighScore);
      saveHighScore(nextHighScore);
    }
  }, [saveHighScore]);

  const getLeaderboardRank = useCallback((candidateScore: number): number | null => {
    if (candidateScore <= 0) return null;
    const list = leaderboard;
    const insertIndex = list.findIndex((entry) => candidateScore > entry.score);
    if (insertIndex !== -1) return insertIndex + 1;
    if (list.length < LEADERBOARD_LIMIT) return list.length + 1;
    return null;
  }, [leaderboard]);

  const submitLeaderboardEntry = useCallback(() => {
    const finalScore = score;
    const trimmedName = playerName.trim().slice(0, 20);
    if (hasSavedScore) return;
    if (finalScore <= 0) return;
    if (!trimmedName) return;
    if (!getLeaderboardRank(finalScore)) return;

    const entry: LeaderboardEntry = {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      name: trimmedName,
      score: finalScore,
      createdAt: Date.now(),
    };

    const next = [...leaderboard, entry]
      .sort((a, b) => (b.score - a.score) || (a.createdAt - b.createdAt))
      .slice(0, LEADERBOARD_LIMIT);

    setLeaderboard(next);
    persistLeaderboard(next);
    setHasSavedScore(true);
  }, [getLeaderboardRank, hasSavedScore, leaderboard, persistLeaderboard, playerName, score]);

  const clearLeaderboard = useCallback(() => {
    try {
      localStorage.removeItem("spaceGameLeaderboard");
    } catch (error) {
      console.error("Failed to clear leaderboard:", error);
    }
    setLeaderboard([]);
  }, []);

  // 初始化星星背景
  const initStars = useCallback(() => {
    const stars: Star[] = [];
    for (let i = 0; i < 100; i++) {
      stars.push({
        x: Math.random() * CANVAS_WIDTH,
        y: Math.random() * CANVAS_HEIGHT,
        size: Math.random() * 2 + 1,
        speed: Math.random() * 2 + 0.5,
      });
    }
    starsRef.current = stars;
  }, []);

  // 碰撞检测
  const checkCollision = (a: GameObject, b: GameObject): boolean => {
    return (
      a.x < b.x + b.width &&
      a.x + a.width > b.x &&
      a.y < b.y + b.height &&
      a.y + a.height > b.y
    );
  };

  // 创建爆炸粒子
  const createExplosion = (x: number, y: number, color: string) => {
    for (let i = 0; i < 15; i++) {
      const angle = (Math.PI * 2 * i) / 15;
      const speed = Math.random() * 4 + 2;
      particlesRef.current.push({
        x,
        y,
        vx: Math.cos(angle) * speed,
        vy: Math.sin(angle) * speed,
        life: 30,
        color,
      });
    }
  };

  // 生成敌人
  const spawnEnemy = useCallback(() => {
    const isAsteroid = Math.random() > 0.6;
    const size = isAsteroid ? ASTEROID_SIZE : ENEMY_SIZE;
    enemiesRef.current.push({
      id: enemyIdRef.current++,
      x: Math.random() * (CANVAS_WIDTH - size),
      y: -size,
      width: size,
      height: size,
      type: isAsteroid ? "asteroid" : "enemy",
      health: isAsteroid ? 2 : 1,
    });
  }, []);

  // 发射子弹
  const shoot = useCallback(() => {
    const now = Date.now();
    if (now - lastShotRef.current < 150) return; // 射击冷却
    lastShotRef.current = now;

    const player = playerRef.current;
    bulletsRef.current.push({
      id: bulletIdRef.current++,
      x: player.x + PLAYER_WIDTH / 2 - BULLET_WIDTH / 2,
      y: player.y,
      width: BULLET_WIDTH,
      height: BULLET_HEIGHT,
    });
  }, []);

  // 绘制飞船
  const drawPlayer = (ctx: CanvasRenderingContext2D) => {
    const { x, y } = playerRef.current;
    const centerX = x + PLAYER_WIDTH / 2;
    const time = Date.now();

    ctx.save();

    // 飞船外发光
    ctx.shadowColor = "#00d4ff";
    ctx.shadowBlur = 25;

    // 主机身 - 流线型设计
    const bodyGradient = ctx.createLinearGradient(x, y, x + PLAYER_WIDTH, y + PLAYER_HEIGHT);
    bodyGradient.addColorStop(0, "#1a3a4a");
    bodyGradient.addColorStop(0.3, "#00d4ff");
    bodyGradient.addColorStop(0.5, "#00f5ff");
    bodyGradient.addColorStop(0.7, "#00d4ff");
    bodyGradient.addColorStop(1, "#1a3a4a");

    // 机身主体
    ctx.fillStyle = bodyGradient;
    ctx.beginPath();
    ctx.moveTo(centerX, y); // 尖端
    ctx.bezierCurveTo(
      centerX + 8, y + 15,
      centerX + 12, y + 25,
      centerX + 10, y + 45
    );
    ctx.lineTo(centerX + 18, y + 50);
    ctx.lineTo(centerX + 15, y + 65);
    ctx.lineTo(centerX + 5, y + 55);
    ctx.lineTo(centerX - 5, y + 55);
    ctx.lineTo(centerX - 15, y + 65);
    ctx.lineTo(centerX - 18, y + 50);
    ctx.lineTo(centerX - 10, y + 45);
    ctx.bezierCurveTo(
      centerX - 12, y + 25,
      centerX - 8, y + 15,
      centerX, y
    );
    ctx.closePath();
    ctx.fill();

    ctx.shadowBlur = 0;

    // 左机翼
    const wingGradient = ctx.createLinearGradient(x - 5, y + 30, x + 15, y + 55);
    wingGradient.addColorStop(0, "#005577");
    wingGradient.addColorStop(0.5, "#00aacc");
    wingGradient.addColorStop(1, "#003344");

    ctx.fillStyle = wingGradient;
    ctx.beginPath();
    ctx.moveTo(centerX - 10, y + 35);
    ctx.lineTo(x - 5, y + 50);
    ctx.lineTo(x, y + 65);
    ctx.lineTo(centerX - 8, y + 55);
    ctx.closePath();
    ctx.fill();

    // 右机翼
    ctx.beginPath();
    ctx.moveTo(centerX + 10, y + 35);
    ctx.lineTo(x + PLAYER_WIDTH + 5, y + 50);
    ctx.lineTo(x + PLAYER_WIDTH, y + 65);
    ctx.lineTo(centerX + 8, y + 55);
    ctx.closePath();
    ctx.fill();

    // 驾驶舱 - 发光玻璃罩
    const cockpitGradient = ctx.createRadialGradient(
      centerX, y + 22, 2,
      centerX, y + 25, 12
    );
    cockpitGradient.addColorStop(0, "#ffffff");
    cockpitGradient.addColorStop(0.3, "#88ffff");
    cockpitGradient.addColorStop(0.7, "#0088aa");
    cockpitGradient.addColorStop(1, "#004455");

    ctx.fillStyle = cockpitGradient;
    ctx.beginPath();
    ctx.ellipse(centerX, y + 25, 6, 10, 0, 0, Math.PI * 2);
    ctx.fill();

    // 驾驶舱高光
    ctx.fillStyle = "rgba(255, 255, 255, 0.6)";
    ctx.beginPath();
    ctx.ellipse(centerX - 2, y + 20, 2, 4, -0.3, 0, Math.PI * 2);
    ctx.fill();

    // 机身装饰线条
    ctx.strokeStyle = "#00ffff";
    ctx.lineWidth = 1;
    ctx.globalAlpha = 0.7;
    
    // 左侧装饰线
    ctx.beginPath();
    ctx.moveTo(centerX - 6, y + 38);
    ctx.lineTo(centerX - 8, y + 50);
    ctx.stroke();
    
    // 右侧装饰线
    ctx.beginPath();
    ctx.moveTo(centerX + 6, y + 38);
    ctx.lineTo(centerX + 8, y + 50);
    ctx.stroke();

    ctx.globalAlpha = 1;

    // 引擎喷口
    ctx.fillStyle = "#334455";
    ctx.beginPath();
    ctx.ellipse(centerX - 8, y + 58, 4, 3, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(centerX + 8, y + 58, 4, 3, 0, 0, Math.PI * 2);
    ctx.fill();

    // 引擎火焰 - 左引擎
    const flameLength1 = 15 + Math.sin(time / 40) * 8 + Math.random() * 3;
    const flameLength2 = 15 + Math.sin(time / 40 + 1) * 8 + Math.random() * 3;

    // 外层火焰（橙红色）
    const flameGradient1 = ctx.createLinearGradient(0, y + 58, 0, y + 58 + flameLength1);
    flameGradient1.addColorStop(0, "#ff6600");
    flameGradient1.addColorStop(0.4, "#ff3300");
    flameGradient1.addColorStop(1, "rgba(255, 0, 0, 0)");

    ctx.fillStyle = flameGradient1;
    ctx.beginPath();
    ctx.moveTo(centerX - 12, y + 58);
    ctx.quadraticCurveTo(centerX - 8, y + 58 + flameLength1 * 0.7, centerX - 8, y + 58 + flameLength1);
    ctx.quadraticCurveTo(centerX - 4, y + 58 + flameLength1 * 0.7, centerX - 4, y + 58);
    ctx.closePath();
    ctx.fill();

    // 内层火焰（黄白色）
    const innerFlameGradient1 = ctx.createLinearGradient(0, y + 58, 0, y + 58 + flameLength1 * 0.6);
    innerFlameGradient1.addColorStop(0, "#ffffff");
    innerFlameGradient1.addColorStop(0.3, "#ffff88");
    innerFlameGradient1.addColorStop(1, "rgba(255, 200, 0, 0)");

    ctx.fillStyle = innerFlameGradient1;
    ctx.beginPath();
    ctx.moveTo(centerX - 10, y + 58);
    ctx.quadraticCurveTo(centerX - 8, y + 58 + flameLength1 * 0.4, centerX - 8, y + 58 + flameLength1 * 0.6);
    ctx.quadraticCurveTo(centerX - 6, y + 58 + flameLength1 * 0.4, centerX - 6, y + 58);
    ctx.closePath();
    ctx.fill();

    // 右引擎火焰
    const flameGradient2 = ctx.createLinearGradient(0, y + 58, 0, y + 58 + flameLength2);
    flameGradient2.addColorStop(0, "#ff6600");
    flameGradient2.addColorStop(0.4, "#ff3300");
    flameGradient2.addColorStop(1, "rgba(255, 0, 0, 0)");

    ctx.fillStyle = flameGradient2;
    ctx.beginPath();
    ctx.moveTo(centerX + 4, y + 58);
    ctx.quadraticCurveTo(centerX + 8, y + 58 + flameLength2 * 0.7, centerX + 8, y + 58 + flameLength2);
    ctx.quadraticCurveTo(centerX + 12, y + 58 + flameLength2 * 0.7, centerX + 12, y + 58);
    ctx.closePath();
    ctx.fill();

    // 内层火焰
    const innerFlameGradient2 = ctx.createLinearGradient(0, y + 58, 0, y + 58 + flameLength2 * 0.6);
    innerFlameGradient2.addColorStop(0, "#ffffff");
    innerFlameGradient2.addColorStop(0.3, "#ffff88");
    innerFlameGradient2.addColorStop(1, "rgba(255, 200, 0, 0)");

    ctx.fillStyle = innerFlameGradient2;
    ctx.beginPath();
    ctx.moveTo(centerX + 6, y + 58);
    ctx.quadraticCurveTo(centerX + 8, y + 58 + flameLength2 * 0.4, centerX + 8, y + 58 + flameLength2 * 0.6);
    ctx.quadraticCurveTo(centerX + 10, y + 58 + flameLength2 * 0.4, centerX + 10, y + 58);
    ctx.closePath();
    ctx.fill();

    // 引擎发光效果
    ctx.shadowColor = "#ff6600";
    ctx.shadowBlur = 15;
    ctx.fillStyle = "rgba(255, 100, 0, 0.3)";
    ctx.beginPath();
    ctx.ellipse(centerX - 8, y + 60, 5, 3, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.beginPath();
    ctx.ellipse(centerX + 8, y + 60, 5, 3, 0, 0, Math.PI * 2);
    ctx.fill();

    ctx.restore();
  };

  // 绘制子弹
  const drawBullets = (ctx: CanvasRenderingContext2D) => {
    bulletsRef.current.forEach((bullet) => {
      ctx.save();
      
      // 子弹尾迹
      const trailGradient = ctx.createLinearGradient(
        bullet.x + bullet.width / 2, bullet.y,
        bullet.x + bullet.width / 2, bullet.y + bullet.height + 20
      );
      trailGradient.addColorStop(0, "rgba(0, 255, 255, 0.8)");
      trailGradient.addColorStop(1, "rgba(0, 255, 255, 0)");
      
      ctx.fillStyle = trailGradient;
      ctx.beginPath();
      ctx.moveTo(bullet.x, bullet.y + 5);
      ctx.lineTo(bullet.x + bullet.width / 2, bullet.y);
      ctx.lineTo(bullet.x + bullet.width, bullet.y + 5);
      ctx.lineTo(bullet.x + bullet.width, bullet.y + bullet.height + 15);
      ctx.lineTo(bullet.x, bullet.y + bullet.height + 15);
      ctx.closePath();
      ctx.fill();

      // 子弹核心
      ctx.shadowColor = "#00ffff";
      ctx.shadowBlur = 10;
      
      const coreGradient = ctx.createLinearGradient(
        bullet.x, bullet.y,
        bullet.x + bullet.width, bullet.y
      );
      coreGradient.addColorStop(0, "#00aaff");
      coreGradient.addColorStop(0.5, "#ffffff");
      coreGradient.addColorStop(1, "#00aaff");
      
      ctx.fillStyle = coreGradient;
      ctx.beginPath();
      ctx.roundRect(bullet.x, bullet.y, bullet.width, bullet.height, 2);
      ctx.fill();

      ctx.restore();
    });
  };

  // 绘制敌人
  const drawEnemies = (ctx: CanvasRenderingContext2D) => {
    enemiesRef.current.forEach((enemy) => {
      if (enemy.type === "asteroid") {
        // 绘制小行星
        ctx.fillStyle = "#8b7355";
        ctx.beginPath();
        ctx.arc(
          enemy.x + enemy.width / 2,
          enemy.y + enemy.height / 2,
          enemy.width / 2,
          0,
          Math.PI * 2
        );
        ctx.fill();
        // 陨石坑
        ctx.fillStyle = "#6b5344";
        ctx.beginPath();
        ctx.arc(enemy.x + enemy.width * 0.3, enemy.y + enemy.height * 0.4, 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.beginPath();
        ctx.arc(enemy.x + enemy.width * 0.7, enemy.y + enemy.height * 0.6, 4, 0, Math.PI * 2);
        ctx.fill();
      } else {
        // 绘制敌机
        ctx.fillStyle = "#ff3366";
        ctx.shadowColor = "#ff3366";
        ctx.shadowBlur = 10;
        ctx.beginPath();
        ctx.moveTo(enemy.x + enemy.width / 2, enemy.y + enemy.height);
        ctx.lineTo(enemy.x + enemy.width, enemy.y);
        ctx.lineTo(enemy.x + enemy.width / 2, enemy.y + enemy.height * 0.3);
        ctx.lineTo(enemy.x, enemy.y);
        ctx.closePath();
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    });
  };

  // 绘制粒子
  const drawParticles = (ctx: CanvasRenderingContext2D) => {
    particlesRef.current.forEach((particle) => {
      ctx.globalAlpha = particle.life / 30;
      ctx.fillStyle = particle.color;
      ctx.beginPath();
      ctx.arc(particle.x, particle.y, 3, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
  };

  // 绘制星星背景
  const drawStars = (ctx: CanvasRenderingContext2D) => {
    ctx.fillStyle = "#ffffff";
    starsRef.current.forEach((star) => {
      ctx.globalAlpha = 0.5 + Math.random() * 0.5;
      ctx.beginPath();
      ctx.arc(star.x, star.y, star.size, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
  };

  // 游戏主循环
  const gameLoop = useCallback(() => {
    const loop = () => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return;

      // 清空画布
      ctx.fillStyle = "#0a0a1a";
      ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

      // 更新和绘制星星
      starsRef.current.forEach((star) => {
        star.y += star.speed;
        if (star.y > CANVAS_HEIGHT) {
          star.y = 0;
          star.x = Math.random() * CANVAS_WIDTH;
        }
      });
      drawStars(ctx);

      // 玩家移动
      const player = playerRef.current;
      if (keysRef.current.has("ArrowLeft") || keysRef.current.has("a")) {
        player.x = Math.max(0, player.x - PLAYER_SPEED);
      }
      if (keysRef.current.has("ArrowRight") || keysRef.current.has("d")) {
        player.x = Math.min(CANVAS_WIDTH - PLAYER_WIDTH, player.x + PLAYER_SPEED);
      }
      if (keysRef.current.has("ArrowUp") || keysRef.current.has("w")) {
        player.y = Math.max(0, player.y - PLAYER_SPEED);
      }
      if (keysRef.current.has("ArrowDown") || keysRef.current.has("s")) {
        player.y = Math.min(CANVAS_HEIGHT - PLAYER_HEIGHT, player.y + PLAYER_SPEED);
      }
      if (keysRef.current.has(" ")) {
        shoot();
      }

      // 更新子弹
      bulletsRef.current = bulletsRef.current.filter((bullet) => {
        bullet.y -= BULLET_SPEED;
        return bullet.y > -BULLET_HEIGHT;
      });

      // 更新敌人
      enemiesRef.current = enemiesRef.current.filter((enemy) => {
        const speed = enemy.type === "asteroid" ? ASTEROID_SPEED : ENEMY_SPEED;
        enemy.y += speed;

        // 检查与玩家碰撞
        if (
          checkCollision(enemy, {
            x: player.x,
            y: player.y,
            width: PLAYER_WIDTH,
            height: PLAYER_HEIGHT,
          })
        ) {
          createExplosion(player.x + PLAYER_WIDTH / 2, player.y + PLAYER_HEIGHT / 2, "#00d4ff");
          updateHighScore(scoreRef.current);
          setGameState("gameOver");
          return false;
        }

        return enemy.y < CANVAS_HEIGHT;
      });

      // 子弹与敌人碰撞
      bulletsRef.current = bulletsRef.current.filter((bullet) => {
        let bulletHit = false;
        enemiesRef.current = enemiesRef.current.filter((enemy) => {
          if (checkCollision(bullet, enemy)) {
            enemy.health--;
            bulletHit = true;
            if (enemy.health <= 0) {
              createExplosion(
                enemy.x + enemy.width / 2,
                enemy.y + enemy.height / 2,
                enemy.type === "asteroid" ? "#8b7355" : "#ff3366"
              );
              const points = enemy.type === "asteroid" ? 20 : 10;
              scoreRef.current += points;
              setScore(scoreRef.current);
              return false;
            }
          }
          return true;
        });
        return !bulletHit;
      });

      // 更新粒子
      particlesRef.current = particlesRef.current.filter((particle) => {
        particle.x += particle.vx;
        particle.y += particle.vy;
        particle.life--;
        return particle.life > 0;
      });

      // 生成敌人
      frameRef.current++;
      const spawnRate = Math.max(30, 60 - Math.floor(scoreRef.current / 100));
      if (frameRef.current % spawnRate === 0) {
        spawnEnemy();
      }

      // 绘制所有元素
      drawPlayer(ctx);
      drawBullets(ctx);
      drawEnemies(ctx);
      drawParticles(ctx);

      // 绘制分数
      ctx.fillStyle = "#ffffff";
      ctx.font = "bold 24px Arial";
      ctx.textAlign = "left";
      ctx.fillText(`分数: ${scoreRef.current}`, 20, 40);

      animationRef.current = requestAnimationFrame(loop);
    };

    loop();
  }, [shoot, spawnEnemy, updateHighScore]);

  // 开始游戏
  const startGame = useCallback(() => {
    playerRef.current = { x: CANVAS_WIDTH / 2 - PLAYER_WIDTH / 2, y: CANVAS_HEIGHT - 80 };
    bulletsRef.current = [];
    enemiesRef.current = [];
    particlesRef.current = [];
    scoreRef.current = 0;
    frameRef.current = 0;
    setScore(0);
    setIsNewRecord(false);
    setHasSavedScore(false);
    setGameState("playing");
    initStars();
  }, [initStars]);

  useEffect(() => {
    if (gameState !== "gameOver") return;
    const rank = getLeaderboardRank(score);
    if (!rank) return;
    window.setTimeout(() => nameInputRef.current?.focus(), 0);
  }, [gameState, getLeaderboardRank, score]);

  // 键盘事件
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      keysRef.current.add(e.key);
      if (e.key === " ") {
        e.preventDefault();
      }
      if (gameState === "gameOver" && e.key === "Enter") {
        const rank = getLeaderboardRank(score);
        if (rank && !hasSavedScore && playerName.trim()) {
          e.preventDefault();
          submitLeaderboardEntry();
          return;
        }
      }
      if (gameState === "menu" && e.key === "Enter") {
        startGame();
      }
      if (gameState === "gameOver" && e.key === "Enter") {
        startGame();
      }
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      keysRef.current.delete(e.key);
    };

    window.addEventListener("keydown", handleKeyDown);
    window.addEventListener("keyup", handleKeyUp);

    return () => {
      window.removeEventListener("keydown", handleKeyDown);
      window.removeEventListener("keyup", handleKeyUp);
    };
  }, [gameState, getLeaderboardRank, hasSavedScore, playerName, score, startGame, submitLeaderboardEntry]);

  // 游戏循环控制
  useEffect(() => {
    if (gameState === "playing") {
      animationRef.current = requestAnimationFrame(gameLoop);
    }
    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, [gameState, gameLoop]);

  // 初始化星星
  useEffect(() => {
    initStars();
  }, [initStars]);

  // 绘制菜单背景
  useEffect(() => {
    if (gameState !== "playing") {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (!canvas || !ctx) return;

      const drawBackground = () => {
        ctx.fillStyle = "#0a0a1a";
        ctx.fillRect(0, 0, CANVAS_WIDTH, CANVAS_HEIGHT);

        starsRef.current.forEach((star) => {
          star.y += star.speed * 0.5;
          if (star.y > CANVAS_HEIGHT) {
            star.y = 0;
            star.x = Math.random() * CANVAS_WIDTH;
          }
        });
        drawStars(ctx);

        if (gameState === "menu") {
          requestAnimationFrame(drawBackground);
        }
      };

      if (gameState === "menu") {
        drawBackground();
      }
    }
  }, [gameState]);

  const leaderboardRank = gameState === "gameOver" ? getLeaderboardRank(score) : null;

  return (
    <div className="relative flex flex-col items-center justify-center">
      <canvas
        ref={canvasRef}
        width={CANVAS_WIDTH}
        height={CANVAS_HEIGHT}
        className="border-2 border-cyan-500 rounded-lg shadow-lg shadow-cyan-500/30"
      />

      {/* 菜单界面 */}
      {gameState === "menu" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/70 rounded-lg">
          <h1 className="text-5xl font-bold text-cyan-400 mb-4 tracking-wider">太空大战</h1>
          <p className="text-gray-400 mb-2">使用 WASD 或 方向键 移动</p>
          <p className="text-gray-400 mb-8">按 空格键 发射子弹</p>
          <button
            onClick={startGame}
            className="px-8 py-3 bg-cyan-500 text-black font-bold rounded-full hover:bg-cyan-400 transition-colors text-xl"
          >
            开始游戏
          </button>
          <p className="text-gray-500 mt-4 text-sm">或按 Enter 键开始</p>

          <div className="mt-8 w-full max-w-md px-6">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-cyan-300 font-bold tracking-wider">排行榜 Top {LEADERBOARD_LIMIT}</h2>
              <button
                onClick={clearLeaderboard}
                className="text-xs text-gray-400 hover:text-gray-200 transition-colors"
              >
                清空
              </button>
            </div>
            {leaderboard.length === 0 ? (
              <p className="text-gray-500 text-sm">暂无记录，来一局创造首条吧。</p>
            ) : (
              <ol className="text-sm text-gray-200 space-y-1">
                {leaderboard.map((entry, index) => (
                  <li key={entry.id} className="flex items-baseline justify-between">
                    <span className="truncate">
                      <span className="text-gray-400 mr-2">#{index + 1}</span>
                      <span className="font-semibold text-white">{entry.name}</span>
                      <span className="text-gray-400 ml-2 text-xs">
                        {new Date(entry.createdAt).toLocaleString()}
                      </span>
                    </span>
                    <span className="font-mono text-cyan-200">{entry.score}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        </div>
      )}

      {/* 游戏结束界面 */}
      {gameState === "gameOver" && (
        <div className="absolute inset-0 flex flex-col items-center justify-center bg-black/80 rounded-lg">
          <h1 className="text-5xl font-bold text-red-500 mb-4">游戏结束</h1>
          <p className="text-2xl text-white mb-2">得分: {score}</p>
          {isNewRecord && score > 0 && (
            <p className="text-yellow-400 mb-2">新纪录!</p>
          )}
          <p className="text-gray-400 mb-8">最高分: {highScore}</p>

          {leaderboardRank && !hasSavedScore && (
            <div className="w-full max-w-md px-6 mb-6">
              <p className="text-cyan-300 text-sm mb-2">恭喜进入排行榜：第 #{leaderboardRank} 名</p>
              <div className="flex gap-2">
                <input
                  ref={nameInputRef}
                  value={playerName}
                  onChange={(e) => setPlayerName(e.target.value)}
                  maxLength={20}
                  placeholder="输入昵称（最多 20 字）"
                  className="flex-1 px-3 py-2 rounded-md bg-black/50 border border-cyan-500/40 text-gray-100 placeholder:text-gray-500 outline-none focus:border-cyan-400"
                />
                <button
                  onClick={submitLeaderboardEntry}
                  disabled={!playerName.trim()}
                  className="px-4 py-2 bg-cyan-500 disabled:bg-cyan-500/40 disabled:text-black/60 text-black font-bold rounded-md hover:bg-cyan-400 transition-colors"
                >
                  提交
                </button>
              </div>
              <p className="text-gray-500 text-xs mt-2">也可以按 Enter 提交，然后再按 Enter 重新开始。</p>
            </div>
          )}

          <div className="w-full max-w-md px-6 mb-8">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-cyan-300 font-bold tracking-wider">排行榜 Top {LEADERBOARD_LIMIT}</h2>
              <button
                onClick={clearLeaderboard}
                className="text-xs text-gray-400 hover:text-gray-200 transition-colors"
              >
                清空
              </button>
            </div>
            {leaderboard.length === 0 ? (
              <p className="text-gray-500 text-sm">暂无记录。</p>
            ) : (
              <ol className="text-sm text-gray-200 space-y-1">
                {leaderboard.map((entry, index) => (
                  <li key={entry.id} className="flex items-baseline justify-between">
                    <span className="truncate">
                      <span className="text-gray-400 mr-2">#{index + 1}</span>
                      <span className="font-semibold text-white">{entry.name}</span>
                      <span className="text-gray-400 ml-2 text-xs">
                        {new Date(entry.createdAt).toLocaleString()}
                      </span>
                    </span>
                    <span className="font-mono text-cyan-200">{entry.score}</span>
                  </li>
                ))}
              </ol>
            )}
          </div>

          <button
            onClick={startGame}
            className="px-8 py-3 bg-cyan-500 text-black font-bold rounded-full hover:bg-cyan-400 transition-colors text-xl"
          >
            再来一局
          </button>
          <p className="text-gray-500 mt-4 text-sm">或按 Enter 键重新开始</p>
        </div>
      )}
    </div>
  );
}
