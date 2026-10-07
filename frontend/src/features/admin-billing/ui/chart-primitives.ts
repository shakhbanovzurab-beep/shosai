// Recharts is only re-exported here: the revenue chart is loaded on demand with next/dynamic,
// which keeps the library out of the page's initial bundle.
export { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
