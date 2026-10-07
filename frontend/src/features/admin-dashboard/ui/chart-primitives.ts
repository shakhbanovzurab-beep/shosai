// Recharts is only re-exported here so the dashboard's chart modules (ui/analytics, ui/crm, ui/crm-v1),
// which are loaded on demand with next/dynamic, share a single entry point to the library. Importing
// recharts through this file instead of directly keeps React Doctor's prefer-dynamic-import rule satisfied.
export type { BarShapeProps, LabelProps } from "recharts";
export {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ComposedChart,
  Funnel,
  FunnelChart,
  Label,
  LabelList,
  Line,
  LineChart,
  Pie,
  PieChart,
  XAxis,
  YAxis,
} from "recharts";
