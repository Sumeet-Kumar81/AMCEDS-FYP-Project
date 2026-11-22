import { ApiClient, apiBaseUrl } from "@amceds/shared";

/** The one API client of this app (tokens live in its memory store). */
export const api = new ApiClient({ baseUrl: apiBaseUrl() });
