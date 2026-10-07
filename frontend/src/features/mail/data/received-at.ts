// Demo timestamps relative to now, so the inbox always looks freshly delivered.
export const minutesAgo = (minutes: number) => new Date(Date.now() - minutes * 60_000).toISOString();
export const hoursAgo = (hours: number) => minutesAgo(hours * 60);
export const daysAgo = (days: number) => hoursAgo(days * 24);
