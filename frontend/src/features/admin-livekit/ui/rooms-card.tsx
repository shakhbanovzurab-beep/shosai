"use client";

import { useState } from "react";

import { ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import type { LiveKitRoom } from "../domain/contract";
import { formatDuration, formatInteger, formatTime } from "../domain/format";
import { RoomSheet } from "./room-sheet";
import { EgressBadge } from "./status-badge";

const codecs = (room: LiveKitRoom) => [room.video_codec, room.audio_codec].filter(Boolean).join(" · ") || "—";

export function RoomsCard({ rooms, updatedAt }: { rooms: LiveKitRoom[]; updatedAt: string }) {
  // The room stays selected while the sheet animates closed.
  const [selected, setSelected] = useState<LiveKitRoom | null>(null);
  const [open, setOpen] = useState(false);

  function openRoom(room: LiveKitRoom) {
    setSelected(room);
    setOpen(true);
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Активные комнаты</CardTitle>
        <CardDescription>Откройте комнату, чтобы увидеть участников и управлять встречей.</CardDescription>
      </CardHeader>
      <CardContent>
        {rooms.length === 0 ? (
          <p className="py-6 text-center text-muted-foreground text-sm">Сейчас нет идущих встреч.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Комната</TableHead>
                <TableHead>Начало</TableHead>
                <TableHead>Длительность</TableHead>
                <TableHead className="text-right">Участники</TableHead>
                <TableHead>Запись</TableHead>
                <TableHead>Кодеки</TableHead>
                <TableHead>
                  <span className="sr-only">Действия</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rooms.map((room) => (
                <TableRow key={room.name} className="cursor-pointer" onClick={() => openRoom(room)}>
                  <TableCell className="max-w-72 truncate font-mono text-xs">{room.name}</TableCell>
                  <TableCell className="tabular-nums">{formatTime(room.started_at)}</TableCell>
                  <TableCell className="tabular-nums">{formatDuration(room.started_at, updatedAt)}</TableCell>
                  <TableCell className="text-right tabular-nums">{formatInteger(room.num_participants)}</TableCell>
                  <TableCell>
                    {room.recording ? (
                      <EgressBadge status="active" />
                    ) : (
                      <span className="text-muted-foreground">Нет</span>
                    )}
                  </TableCell>
                  <TableCell className="text-muted-foreground">{codecs(room)}</TableCell>
                  <TableCell className="text-right">
                    <Button
                      variant="ghost"
                      size="sm"
                      aria-label={`Участники комнаты ${room.name}`}
                      onClick={(event) => {
                        event.stopPropagation();
                        openRoom(room);
                      }}
                    >
                      Участники
                      <ChevronRight aria-hidden="true" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
      <RoomSheet room={selected} open={open} onOpenChange={setOpen} />
    </Card>
  );
}
