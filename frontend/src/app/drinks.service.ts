import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Drinker } from './shared/drinker';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class DrinksService {

  constructor(private http: HttpClient) { }

  getDrinkers(): Observable<Drinker[]>{
    return this.http.get<Drinker[]>('http://ip:8000/users');
  }

  removeDrinker(person:Drinker){
    //Code to remove
  }

  addDrinker(person:Drinker){
    this.http.post('http://ip:8000/adduser',person).subscribe(x => console.log(x));
  }

  setActive(id:number): Observable<any>{
    return this.http.put(`http://ip:8000/user/active/${id}`,null);
  }
}
