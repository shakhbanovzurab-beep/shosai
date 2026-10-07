import { LockKeyhole } from "lucide-react";

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

import { profile } from "../data/profile";
import { ProfileDocuments } from "./profile-documents";
import { EmploymentDetails } from "./profile-employment-details";
import { ProfileHeader } from "./profile-header";
import { ProfileOverview } from "./profile-overview";
import { PersonalDetails } from "./profile-personal-details";
import { ProfileStatusSidebar } from "./profile-status-sidebar";
import { TimeOffDetails } from "./profile-time-off-details";

export function ProfileScreen() {
  return (
    <div className="flex flex-col gap-4 py-4" data-content-padding="false">
      <Breadcrumb aria-label="Навигационная цепочка" className="px-4">
        <BreadcrumbList>
          <BreadcrumbItem>
            <span>Дашборд</span>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <span>Сотрудники</span>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <span>Справочник сотрудников</span>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <span>{profile.name}</span>
          </BreadcrumbItem>
          <BreadcrumbSeparator />
          <BreadcrumbItem>
            <BreadcrumbPage>Профиль</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <ProfileHeader profile={profile} />

      <Tabs className="min-h-0 flex-1 gap-0" defaultValue="overview">
        <div className="scrollbar-none touch-pan-x overflow-x-auto overscroll-x-contain border-y">
          <TabsList
            className="w-max min-w-full justify-start gap-4 px-4 *:data-[slot=tabs-trigger]:flex-none"
            variant="line"
          >
            <TabsTrigger value="overview">Обзор</TabsTrigger>
            <TabsTrigger value="personal">Личные данные</TabsTrigger>
            <TabsTrigger value="employment">Работа</TabsTrigger>
            <TabsTrigger value="compensation">Вознаграждение</TabsTrigger>
            <TabsTrigger value="time-off">Отпуска</TabsTrigger>
            <TabsTrigger value="documents">Документы</TabsTrigger>
          </TabsList>
        </div>

        <div className="px-4 md:px-6">
          <TabsContent value="overview">
            <div className="grid lg:grid-cols-[minmax(0,1fr)_auto_18rem]">
              <div className="py-4 lg:pr-6">
                <ProfileOverview profile={profile} />
              </div>
              <Separator className="hidden lg:block" orientation="vertical" />
              <div className="py-4 lg:pl-6">
                <ProfileStatusSidebar profile={profile} />
              </div>
            </div>
          </TabsContent>

          <TabsContent className="py-4" value="personal">
            <PersonalDetails profile={profile} />
          </TabsContent>

          <TabsContent className="py-4" value="employment">
            <EmploymentDetails profile={profile} />
          </TabsContent>

          <TabsContent className="py-4" value="compensation">
            <div className="flex items-start gap-3">
              <LockKeyhole aria-hidden="true" className="size-4 text-muted-foreground" />
              <div>
                <p className="font-medium text-sm">Информация с ограниченным доступом</p>
                <p className="mt-0.5 text-muted-foreground text-sm">
                  Доступна HR-администраторам и уполномоченным финансовым ролям.
                </p>
              </div>
            </div>
          </TabsContent>

          <TabsContent className="py-4" value="time-off">
            <TimeOffDetails profile={profile} />
          </TabsContent>

          <TabsContent className="py-4" value="documents">
            <ProfileDocuments documents={profile.documents} />
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
