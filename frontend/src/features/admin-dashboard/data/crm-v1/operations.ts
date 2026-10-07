export const regionSalesData = [
  {
    region: "Северная Америка",
    sales: 37800,
    percentage: 31,
    growth: "-3,2%",
    isPositive: false,
  },
  {
    region: "Европа",
    sales: 40100,
    percentage: 34,
    growth: "+9,4%",
    isPositive: true,
  },
  {
    region: "Азиатско-Тихоокеанский регион",
    sales: 30950,
    percentage: 26,
    growth: "+12,8%",
    isPositive: true,
  },
  {
    region: "Латинская Америка",
    sales: 12200,
    percentage: 7,
    growth: "-1,7%",
    isPositive: false,
  },
  {
    region: "Ближний Восток и Африка",
    sales: 2450,
    percentage: 2,
    growth: "+6,0%",
    isPositive: true,
  },
];

export const actionItems = [
  {
    id: 1,
    title: "Отправить стартовые документы",
    desc: "Отправить документы для онбординга и график работ",
    due: "Срок — сегодня",
    priority: "High",
    priorityColor: "bg-red-100 text-red-700",
    checked: false,
  },
  {
    id: 2,
    title: "Демо-звонок по SaaS MVP",
    desc: "Назначить звонок в Zoom с клиентом",
    due: "Срок — завтра",
    priority: "Medium",
    priorityColor: "bg-yellow-100 text-yellow-700",
    checked: true,
  },
  {
    id: 3,
    title: "Обновить кейс",
    desc: "Добавить последний проект с LLM",
    due: "Срок — на этой неделе",
    priority: "Low",
    priorityColor: "bg-green-100 text-green-700",
    checked: false,
  },
];
