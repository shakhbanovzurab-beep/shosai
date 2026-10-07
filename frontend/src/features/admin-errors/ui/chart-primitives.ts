// Recharts is only re-exported here: the events timeline is loaded on demand with next/dynamic,
// which keeps the library out of the page's initial bundle.
export { Bar, BarChart, CartesianGrid, XAxis, YAxis } from "recharts";
