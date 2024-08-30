export interface Drinker {
    id: number;
    name: string;
    email: string;
    nickname: string;
    quantity: number;
    active: boolean;
    drinks?: Drinks[];
}

export class DrinkerWithQuantities implements Drinker {
  id: number = 0;
  name: string = "";
  email: string = "";
  nickname: string = "";
  quantity: number = this.getTotalDrink();
  active: boolean = false;
  drinks?: Drinks[];

  getTotalDrink():number{
    var values = this.drinks;
    var result;
    if(values===undefined)
      return 0;
    else
      return values.reduce((accumulator,val) => accumulator+val.quantity,0);
  }

  public constructor(init?:Partial<Drinker>){
    Object.assign(this,init);
  }
}


export interface Drinks {
  id: number;
  user_id: number;
  timestamp: Date;
  quantity: number;
}
