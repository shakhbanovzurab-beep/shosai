import { Ellipsis, FileDown, FileUp, RefreshCw, Share2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator } from "@/components/ui/dropdown-menu-items";
import { Select, SelectContent, SelectGroup, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function AnalyticsToolbar() {
  return (
    <div className="flex items-center gap-2">
      <Select defaultValue="last-4-weeks">
        <SelectTrigger className="w-34">
          <SelectValue placeholder="Выберите период" />
        </SelectTrigger>
        <SelectContent>
          <SelectGroup>
            <SelectItem value="last-7-days">За 7 дней</SelectItem>
            <SelectItem value="last-4-weeks">За 4 недели</SelectItem>
            <SelectItem value="last-3-months">За 3 месяца</SelectItem>
            <SelectItem value="year-to-date">С начала года</SelectItem>
          </SelectGroup>
        </SelectContent>
      </Select>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button size="icon" variant="outline" aria-label="Другие действия с аналитикой">
            <Ellipsis />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-56">
          <DropdownMenuGroup>
            <DropdownMenuLabel>Действия с аналитикой</DropdownMenuLabel>
            <DropdownMenuItem>
              <FileDown />
              Экспорт отчёта
            </DropdownMenuItem>
            <DropdownMenuItem>
              <FileUp />
              Импорт данных
            </DropdownMenuItem>
            <DropdownMenuItem>
              <Share2 />
              Поделиться дашбордом
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem>
              <RefreshCw />
              Обновить метрики
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  );
}
