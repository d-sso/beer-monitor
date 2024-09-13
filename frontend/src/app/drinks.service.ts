import { HttpClient } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Drinker } from './shared/drinker';
import { Observable } from 'rxjs';
import { PlatformLocation } from '@angular/common';
import { TemplateBindingParseResult } from '@angular/compiler';

@Injectable({
  providedIn: 'root'
})

export class DrinksService {
  
  base_url:string = "";

  constructor(private http: HttpClient, location: PlatformLocation) { 
    this.base_url = location.protocol + "//" + location.hostname + ":8000";
    console.log(location.protocol);
    console.log(location.hostname);
    console.log(this.base_url);
  }

  getDrinkers(): Observable<Drinker[]>{
    return this.http.get<Drinker[]>(this.base_url + '/users');
  }

  removeDrinker(person:Drinker){
    //Code to remove
  }

  addDrinker(person:Drinker){
    this.http.post(this.base_url+'/adduser',person).subscribe(x => console.log(x));
  }

  setActive(id:number): Observable<any>{
    return this.http.put(`${this.base_url}/user/active/${id}`,null);
  }
}
