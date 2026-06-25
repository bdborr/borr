export type Paper = {
  id: string;
  openalex_id: string | null;
  title: string;
  authors: string[] | null;
  abstract: string | null;
  doi: string | null;
  url: string | null;
  journal: string | null;
  year: number | null;
  institution: string[] | null;
  fields: string[] | null;
  paper_type: string | null;
  access_type: string | null;
  source: string | null;
  verified: boolean;
  citation_count: number | null;
  created_at: string;
};
