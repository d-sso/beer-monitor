import { Component } from '@angular/core';
import { CommonModule, formatNumber } from "@angular/common";
import { Drinker } from './shared/drinker';
import { ItemComponent } from './item/item.component';
import { DrinksService } from './drinks.service';
import { interval } from 'rxjs';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, ItemComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.css'
})

export class AppComponent {
  title = 'Beer Ranking';
  componentTitle = "Beer Ranking";
  refreshSubscription;
  editing = false;

  refreshDrinkers(){
    var tempDrinkers:Drinker[] = [];
    this.drinksService.getDrinkers().subscribe(item => {
      item.forEach(drinker => {
        var temp = drinker;
        //console.log(temp);
        temp.quantity = temp.drinks!.reduce((accumulator,val) => accumulator+val.quantity,0)
        tempDrinkers.push(temp)
      });
      tempDrinkers.sort((a,b) => b.quantity - a.quantity);
      this.allDrinkers = tempDrinkers;
    });
  }

  constructor(private drinksService: DrinksService){
    this.refreshDrinkers();
    this.refreshSubscription = interval(5000).subscribe(
      val => {
        console.log(val); 
        this.refreshDrinkers();
      }
    );
  }

  filter: "all" | "active" | "active" = "all";

  allDrinkers2 = []

  allDrinkers = [
    { 
      id:0,
      name: "Placeholder",
      nickname: "Place",
      quantity: 0,
      active: false,
      email: '',
    },
  ];

  

  addDrinker(name:string, email:string, nickname:string){
    if(!name) return;
    this.drinksService.addDrinker(
      {
        id:0,
        name:name,
        email:email,
        nickname:nickname,
        active: false,
        quantity:0,
      }
    );

    this.refreshDrinkers();
  }

  remove(item: Drinker){
    this.allDrinkers.splice(this.allDrinkers.indexOf(item),1);
  }

  editableToggle(flag: boolean){
    console.log("toogle!")
    if(flag)
    {
      this.refreshSubscription.unsubscribe()
    }
    else
    {
      this.refreshSubscription = interval(5000).subscribe(
        val => {
          console.log(val); 
          this.refreshDrinkers();
        }
      );
    }
  }

  totalQuantity(): string{
    var total = this.drinkers.reduce((accumulator,val) => accumulator+val.quantity,0);
    return formatNumber(total/1000,"en-US","1.1-1");
  }

  get drinkers() {
    if (this.filter === "all") {
      return this.allDrinkers;
    }

    return this.allDrinkers.filter((item) => 
      this.filter==="active" ? item.active : !item.active
    );
  }
}

