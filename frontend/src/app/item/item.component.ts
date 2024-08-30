import { Component, Input, Output, EventEmitter, ChangeDetectionStrategy, output } from '@angular/core';
import { CommonModule, formatNumber } from '@angular/common';
import { Drinker } from '../shared/drinker';
import { DrinksService } from '../drinks.service';
import { Drinks } from '../shared/drinker';
import { HttpErrorResponse, HttpResponse } from '@angular/common/http';

@Component({
  selector: 'app-item',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './item.component.html',
  styleUrl: './item.component.css',
  changeDetection: ChangeDetectionStrategy.OnPush
})

export class ItemComponent {

  editable = false;

  @Input() item!: Drinker;
  @Output() remove = new EventEmitter<Drinker>();
  @Output() editing = new EventEmitter<boolean>();

  constructor(private drinksService:DrinksService){

  }

  saveItem(name: string) {
    if (!name) return;

    this.item.name = name;
  }

  handleChange(evt: any){
    var target = evt.target;
    if(target){
      this.drinksService.setActive(target.value).subscribe(
        (response) => {
          console.log(response);
        },
        (error:HttpErrorResponse) => {
          console.log(error.status);
        }
      );
    }
  }

  getTotalDrink():string{
    var values = this.item.drinks;
    var result;
    if(values===undefined)
      result = 0;
    else
      result = values.reduce((accumulator,val) => accumulator+val.quantity,0);

    return formatNumber(result/1000,'en-US','1.2-2')
  }

  toggleEdit(){
    this.editable = !this.editable; 
    this.editing.emit(this.editable);
    console.log("Click!");
  }
}
