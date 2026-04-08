import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Drinker } from './shared/drinker';
import { Observable } from 'rxjs';
import { PlatformLocation } from '@angular/common';

export interface DrinkRecord {
  id: number;
  user_id: number | null;
  user_name: string | null;
  timestamp: string;
  quantity: number;
}

export interface PaginatedDrinks {
  items: DrinkRecord[];
  total: number;
  page: number;
  limit: number;
  pages: number;
}

@Injectable({
  providedIn: 'root'
})
export class DrinksService {

  base_url:string = "";

  constructor(private http: HttpClient, location: PlatformLocation) {
    this.base_url = location.protocol + "//" + location.hostname + ":8000";
  }

  getDrinkers(): Observable<Drinker[]>{
    return this.http.get<Drinker[]>(this.base_url + '/users');
  }

  addDrinker(person:Drinker){
    this.http.post(this.base_url+'/adduser',person).subscribe(x => console.log(x));
  }

  setActive(id:number): Observable<any>{
    return this.http.put(`${this.base_url}/user/active/${id}`,null);
  }

  updateUser(id: number, data: { name?: string | null; email?: string | null; nickname?: string | null }): Observable<any> {
    return this.http.patch(`${this.base_url}/user/${id}`, data);
  }

  deleteUser(id: number): Observable<any> {
    return this.http.delete(`${this.base_url}/user/${id}`);
  }

  recordFace(id: number): Observable<any> {
    return this.http.post(`${this.base_url}/recordFace?id=${id}`, null);
  }

  getDrinksPage(page: number = 1, limit: number = 20): Observable<PaginatedDrinks> {
    return this.http.get<PaginatedDrinks>(`${this.base_url}/drinks?page=${page}&limit=${limit}`);
  }

  updateDrink(id: number, data: { user_id?: number | null; quantity?: number }): Observable<any> {
    return this.http.patch(`${this.base_url}/drink/${id}`, data);
  }
}
