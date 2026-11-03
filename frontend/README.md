Owner: Sumeet. Two Vite apps:
  dashboard/  dispatcher + admin (React+TS+Tailwind+Leaflet)
  pwa/        public report page + citizen + driver (mobile-first PWA)
Create:
  cd frontend && rm -f dashboard/.gitkeep pwa/.gitkeep
  npm create vite@latest dashboard -- --template react-ts
  npm create vite@latest pwa -- --template react-ts
API base URL from VITE_API_URL (default http://localhost:8000). Contract = http://localhost:8000/docs
