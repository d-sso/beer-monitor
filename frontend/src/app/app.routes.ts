import { Routes } from '@angular/router';
import { HomeComponent } from './home/home.component';
import { AdminComponent } from './admin/admin.component';
import { DrinkHistoryComponent } from './drink-history/drink-history.component';

export const routes: Routes = [
  { path: '', component: HomeComponent },
  { path: 'admin', component: AdminComponent },
  { path: 'drinks', component: DrinkHistoryComponent },
  { path: '**', redirectTo: '' },
];
