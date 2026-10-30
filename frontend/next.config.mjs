/** @type {import('next').NextConfig} */
const isDesktopBuild = process.env.BHARATDOCS_DESKTOP_BUILD === "1"

const nextConfig = {
  ...(isDesktopBuild ? { output: "export", distDir: ".next-desktop" } : {}),
}

export default nextConfig
