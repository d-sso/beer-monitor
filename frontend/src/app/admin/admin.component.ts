import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { DrinksService } from '../drinks.service';
import { Drinker } from '../shared/drinker';

interface EditableUser extends Drinker {
  editing: boolean;
  editName: string;
  editEmail: string;
  editNickname: string;
}

@Component({
  selector: 'app-admin',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin.component.html',
  styleUrl: './admin.component.css'
})
export class AdminComponent implements OnInit {
  users: EditableUser[] = [];

  constructor(private drinksService: DrinksService, private router: Router) {}

  ngOnInit() {
    this.loadUsers();
  }

  loadUsers() {
    this.drinksService.getDrinkers().subscribe(items => {
      this.users = items.map(u => ({
        ...u,
        editing: false,
        editName: u.name,
        editEmail: u.email ?? '',
        editNickname: u.nickname ?? '',
      }));
    });
  }

  startEdit(user: EditableUser) {
    user.editName = user.name;
    user.editEmail = user.email ?? '';
    user.editNickname = user.nickname ?? '';
    user.editing = true;
  }

  cancelEdit(user: EditableUser) {
    user.editing = false;
  }

  saveUser(user: EditableUser) {
    if (!user.editName.trim()) return;
    this.drinksService.updateUser(user.id, {
      name: user.editName.trim(),
      email: user.editEmail.trim() || null,
      nickname: user.editNickname.trim() || null,
    }).subscribe({
      next: (updated) => {
        user.name = updated.name;
        user.email = updated.email;
        user.nickname = updated.nickname;
        user.editing = false;
      },
      error: (err) => console.error('Failed to update user', err)
    });
  }

  deleteUser(user: EditableUser) {
    if (!confirm(`Delete user "${user.name}"? This cannot be undone.`)) return;
    this.drinksService.deleteUser(user.id).subscribe({
      next: () => {
        this.users = this.users.filter(u => u.id !== user.id);
      },
      error: (err) => console.error('Failed to delete user', err)
    });
  }

  replaceFace(user: EditableUser) {
    this.drinksService.recordFace(user.id).subscribe({
      next: () => this.router.navigate(['/']),
      error: (err) => console.error('Failed to trigger face capture', err)
    });
  }
}
