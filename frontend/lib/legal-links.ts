export function legalHref(page: "" | "terms" | "privacy") {
  const pagePath = page ? `${page}.html` : "index.html"
  return process.env.NEXT_PUBLIC_DESKTOP_APP === "1" ? `./${pagePath}` : page ? `/${page}` : "/"
}
