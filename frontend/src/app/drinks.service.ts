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
    return this.http.get<Drinker[]>('http://192.168.18.2:8000/users');
  }

  removeDrinker(person:Drinker){
    //Code to remove
  }

  addDrinker(person:Drinker){
    this.http.post('http://192.168.18.2:8000/adduser',person).subscribe(x => console.log(x));
  }

  setActive(id:number): Observable<any>{
    return this.http.put(`http://192.168.18.2:8000/user/active/${id}`,null);
  }
}
