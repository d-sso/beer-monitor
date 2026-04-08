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

interface Keg {
  id: number;
  name: string;
  keg_size: number;
  density: number | null;
  active: boolean;
  image_url: string | null;
}

interface EditableKeg extends Keg {
  editing: boolean;
  editName: string;
  editKegSize: number;
  editDensity: string;
  editImageUrl: string;
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
  kegs: EditableKeg[] = [];

  newKeg = { name: '', keg_size: 30, density: '', image_url: '' };

  constructor(private drinksService: DrinksService, private router: Router) {}

  ngOnInit() {
    this.loadUsers();
    this.loadKegs();
  }

  // ── Users ────────────────────────────────────────────────────────────────

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

  startEditUser(user: EditableUser) {
    user.editName = user.name;
    user.editEmail = user.email ?? '';
    user.editNickname = user.nickname ?? '';
    user.editing = true;
  }

  cancelEditUser(user: EditableUser) {
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
      next: () => { this.users = this.users.filter(u => u.id !== user.id); },
      error: (err) => console.error('Failed to delete user', err)
    });
  }

  replaceFace(user: EditableUser) {
    this.drinksService.recordFace(user.id).subscribe({
      next: () => this.router.navigate(['/']),
      error: (err) => console.error('Failed to trigger face capture', err)
    });
  }

  // ── Kegs ─────────────────────────────────────────────────────────────────

  loadKegs() {
    this.drinksService.getKegs().subscribe(items => {
      this.kegs = items.map(k => this.toEditable(k));
    });
  }

  private toEditable(k: Keg): EditableKeg {
    return {
      ...k,
      editing: false,
      editName: k.name,
      editKegSize: k.keg_size,
      editDensity: k.density != null ? String(k.density) : '',
      editImageUrl: k.image_url ?? '',
    };
  }

  startEditKeg(keg: EditableKeg) {
    keg.editName = keg.name;
    keg.editKegSize = keg.keg_size;
    keg.editDensity = keg.density != null ? String(keg.density) : '';
    keg.editImageUrl = keg.image_url ?? '';
    keg.editing = true;
  }

  cancelEditKeg(keg: EditableKeg) {
    keg.editing = false;
  }

  saveKeg(keg: EditableKeg) {
    if (!keg.editName.trim()) return;
    const density = keg.editDensity.trim() ? parseFloat(keg.editDensity) : null;
    this.drinksService.updateKeg(keg.id, {
      name: keg.editName.trim(),
      keg_size: keg.editKegSize,
      density,
      image_url: keg.editImageUrl.trim() || null,
    }).subscribe({
      next: (updated) => {
        Object.assign(keg, this.toEditable(updated));
        keg.editing = false;
      },
      error: (err) => console.error('Failed to update keg', err)
    });
  }

  deleteKeg(keg: EditableKeg) {
    if (!confirm(`Delete keg "${keg.name}"?`)) return;
    this.drinksService.deleteKeg(keg.id).subscribe({
      next: () => { this.kegs = this.kegs.filter(k => k.id !== keg.id); },
      error: (err) => console.error('Failed to delete keg', err)
    });
  }

  activateKeg(keg: EditableKeg) {
    this.drinksService.activateKeg(keg.id).subscribe({
      next: () => {
        this.kegs.forEach(k => k.active = false);
        keg.active = true;
      },
      error: (err) => console.error('Failed to activate keg', err)
    });
  }

  addKeg() {
    if (!this.newKeg.name.trim()) return;
    const density = this.newKeg.density.trim() ? parseFloat(this.newKeg.density) : null;
    this.drinksService.createKeg({
      name: this.newKeg.name.trim(),
      keg_size: this.newKeg.keg_size,
      density,
      image_url: this.newKeg.image_url.trim() || null,
    }).subscribe({
      next: (created) => {
        this.kegs.push(this.toEditable(created));
        this.newKeg = { name: '', keg_size: 30, density: '', image_url: '' };
      },
      error: (err) => console.error('Failed to create keg', err)
    });
  }
}
