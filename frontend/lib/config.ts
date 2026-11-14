/**
 * Gyaan AI - Environment & Runtime Configuration
 */

export const API_BASE_URL: string =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://127.0.0.1:8000";

export const APP_CONFIG = {
  name: "Gyaan AI",
  tagline: "Intelligent Multi-Agent CBSE Educational Platform",
  version: "0.8.2",
  defaultGrade: "Class 10",
  defaultSubject: "Science",
  supportedOrigins: ["http://localhost:3000", "http://127.0.0.1:3000"],
};
