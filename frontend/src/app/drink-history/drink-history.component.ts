import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { DrinksService, DrinkRecord } from '../drinks.service';
import { Drinker } from '../shared/drinker';

interface EditableDrink extends DrinkRecord {
  editUserId: number | null;
  editQuantity: number;
  dirty: boolean;
  saving: boolean;
}

@Component({
  selector: 'app-drink-history',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './drink-history.component.html',
  styleUrl: './drink-history.component.css'
})
export class DrinkHistoryComponent implements OnInit {
  drinks: EditableDrink[] = [];
  users: Drinker[] = [];
  page = 1;
  totalPages = 1;
  total = 0;

  constructor(private drinksService: DrinksService) {}

  ngOnInit() {
    this.loadUsers();
    this.loadPage(1);
  }

  loadUsers() {
    this.drinksService.getDrinkers().subscribe(users => {
      this.users = users;
    });
  }

  loadPage(page: number) {
    this.drinksService.getDrinksPage(page).subscribe(result => {
      this.page = result.page;
      this.totalPages = result.pages;
      this.total = result.total;
      this.drinks = result.items.map(d => ({
        ...d,
        editUserId: d.user_id,
        editQuantity: d.quantity,
        dirty: false,
        saving: false,
      }));
    });
  }

  markDirty(drink: EditableDrink) {
    drink.dirty = true;
  }

  confirm(drink: EditableDrink) {
    drink.saving = true;
    this.drinksService.updateDrink(drink.id, {
      user_id: drink.editUserId ?? undefined,
      quantity: drink.editQuantity,
    }).subscribe({
      next: () => {
        drink.user_id = drink.editUserId;
        drink.quantity = drink.editQuantity;
        drink.user_name = this.users.find(u => u.id === drink.editUserId)?.name ?? null;
        drink.dirty = false;
        drink.saving = false;
      },
      error: (err) => {
        console.error('Failed to update drink', err);
        drink.saving = false;
      }
    });
  }

  prevPage() {
    if (this.page > 1) this.loadPage(this.page - 1);
  }

  nextPage() {
    if (this.page < this.totalPages) this.loadPage(this.page + 1);
  }
}
