/** Vite/Vitest `?raw` imports (tests read the backend permission catalog as text). */
declare module "*?raw" {
  const content: string;
  export default content;
}
