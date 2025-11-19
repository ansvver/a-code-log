// router.tsx
import {
    createRouter,
    createRoute,
    Outlet,
    RouterProvider,
    Link,
  } from '@tanstack/react-router'
  import React from 'react'
  
  // Layout 作为根节点
  const Root = () => (
    <div>
      <h1>My App</h1>
      <nav>
        <Link to="/">Home</Link> | <Link to="/about">About</Link>
      </nav>
      <hr />
      <Outlet /> {/* 渲染子路由 */}
    </div>
  )
  
  const rootRoute = createRoute({
    id: 'root',
    component: Root,
  })
  
  // Home
  const indexRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/',
    component: () => <div>Home Page</div>,
  })
  
  // About
  const aboutRoute = createRoute({
    getParentRoute: () => rootRoute,
    path: '/about',
    component: () => <div>About Page</div>,
  })
  
  // 构建路由树
  const routeTree = rootRoute.addChildren([indexRoute, aboutRoute])
  
  // 创建路由实例
  export const router = createRouter({ routeTree })
  
  // 让 TypeScript 自动推断路由类型（必写）
  declare module '@tanstack/react-router' {
    interface Register {
      router: typeof router
    }
  }
  