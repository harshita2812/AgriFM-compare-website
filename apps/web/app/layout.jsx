import "../../../src/styles.css";
import "./provenance.css";

export const metadata = {
  title: "AgriFM Compare — Model evaluation for Indian agriculture",
  description: "A region-controlled research workflow for precision agriculture foundation models.",
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
