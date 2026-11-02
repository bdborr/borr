import type { MetadataRoute } from "next";
import { getTopPapersForSitemap } from "@/lib/turso-papers";
import { getSiteUrl } from "@/lib/site-url";

export const revalidate = 86400; // Cache sitemap for 24 hours

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const siteUrl = getSiteUrl();

  const staticRoutes: MetadataRoute.Sitemap = [
    {
      url: `${siteUrl}`,
      lastModified: new Date(),
      changeFrequency: "daily",
      priority: 1.0,
    },
    {
      url: `${siteUrl}/about`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/submit`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.8,
    },
    {
      url: `${siteUrl}/contact`,
      lastModified: new Date(),
      changeFrequency: "monthly",
      priority: 0.7,
    },
    {
      url: `${siteUrl}/terms`,
      lastModified: new Date(),
      changeFrequency: "yearly",
      priority: 0.5,
    },
    {
      url: `${siteUrl}/policy`,
      lastModified: new Date(),
      changeFrequency: "yearly",
      priority: 0.5,
    },
  ];

  try {
    const papers = await getTopPapersForSitemap(250);
    const paperRoutes: MetadataRoute.Sitemap = papers.map((paper) => {
      const identifier = paper.doi || paper.id;
      return {
        url: `${siteUrl}/paper/${encodeURIComponent(identifier)}`,
        lastModified: paper.updated_at ? new Date(paper.updated_at) : new Date(),
        changeFrequency: "weekly" as const,
        priority: 0.7,
      };
    });

    return [...staticRoutes, ...paperRoutes];
  } catch {
    return staticRoutes;
  }
}
