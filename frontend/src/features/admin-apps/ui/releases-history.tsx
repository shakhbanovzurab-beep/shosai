"use client";

import { History } from "lucide-react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty";
import { Table, TableBody, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { APP_PLATFORMS, type AppPlatform, type AppRelease } from "../domain/contract";
import { PLATFORM_LABELS } from "../domain/format";
import { ReleaseRow } from "./release-row";

export function ReleasesHistory({ releases }: { releases: readonly AppRelease[] }) {
  const byPlatform = Object.fromEntries(
    APP_PLATFORMS.map((platform) => [platform, releases.filter((r) => r.platform === platform)]),
  ) as Record<AppPlatform, AppRelease[]>;

  return (
    <Card>
      <CardHeader>
        <CardTitle>История сборок</CardTitle>
        <CardDescription>
          Новые сборки загружаются черновиками. Опубликованные стабильные сборки можно раскатывать поэтапно.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Tabs defaultValue="macos" className="gap-4">
          <TabsList>
            {APP_PLATFORMS.map((platform) => (
              <TabsTrigger key={platform} value={platform}>
                {PLATFORM_LABELS[platform]}
                <span className="text-muted-foreground tabular-nums">{byPlatform[platform].length}</span>
              </TabsTrigger>
            ))}
          </TabsList>
          {APP_PLATFORMS.map((platform) => (
            <TabsContent key={platform} value={platform}>
              {byPlatform[platform].length === 0 ? (
                <Empty className="border border-dashed">
                  <EmptyHeader>
                    <EmptyMedia variant="icon">
                      <History />
                    </EmptyMedia>
                    <EmptyTitle>Сборок пока нет</EmptyTitle>
                    <EmptyDescription>
                      Загрузите первую сборку для {PLATFORM_LABELS[platform]} — она появится здесь черновиком.
                    </EmptyDescription>
                  </EmptyHeader>
                </Empty>
              ) : (
                <div className="overflow-hidden rounded-lg border">
                  <Table>
                    <TableHeader className="bg-muted/50">
                      <TableRow>
                        <TableHead>Версия</TableHead>
                        <TableHead>Канал</TableHead>
                        <TableHead>Архитектура</TableHead>
                        <TableHead className="text-right">Размер</TableHead>
                        <TableHead>Загружено</TableHead>
                        <TableHead>Статус</TableHead>
                        <TableHead>Раскатка</TableHead>
                        <TableHead className="text-right">Загрузки</TableHead>
                        <TableHead>
                          <span className="sr-only">Действия</span>
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {byPlatform[platform].map((release) => (
                        <ReleaseRow key={release.id} release={release} />
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}
            </TabsContent>
          ))}
        </Tabs>
      </CardContent>
    </Card>
  );
}
