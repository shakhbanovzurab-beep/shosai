// Recharts is only re-exported here so the spend chart, which is loaded on demand with
// next/dynamic from spend-chart.tsx, keeps the library out of the page's initial bundle.
export { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";
