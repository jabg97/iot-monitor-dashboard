import { NgModule } from '@angular/core';
import { RouterModule, Routes } from '@angular/router';
import { DashboardComponent } from 'src/pages/dashboard/dashboard.component';
import { DeveloperComponent } from 'src/pages/developer/developer.component';
import { DevicesComponent } from 'src/pages/devices/devices.component';
import { NotFoundComponent } from 'src/pages/not-found/not-found.component';

const routes: Routes = [
  {
    path: '',
    component: DashboardComponent,
  },
  {
    path: 'devices',
    component: DevicesComponent,
  },
  {
    path: 'developer',
    component: DeveloperComponent,
  },
  {
    path: '**',
    component: NotFoundComponent,
  },
];

@NgModule({
  imports: [RouterModule.forRoot(routes)],
  exports: [RouterModule],
})
export class AppRoutingModule {}
