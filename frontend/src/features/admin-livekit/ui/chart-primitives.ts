// Recharts is only re-exported here: the history charts is loaded on demand with next/dynamic,
// which keeps the library out of the page's initial bundle.
export { Area, AreaChart, CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
