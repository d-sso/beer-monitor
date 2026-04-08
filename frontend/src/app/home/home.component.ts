import { Component } from '@angular/core';
import { CommonModule, formatNumber } from "@angular/common";
import { Drinker } from '../shared/drinker';
import { ItemComponent } from '../item/item.component';
import { DrinksService } from '../drinks.service';
import { interval, Observable } from 'rxjs';
import { WebcamImage, WebcamModule } from 'ngx-webcam';
import {webSocket} from "rxjs/webSocket";

interface DetectApp{
  n_images:Number;
  saved_images:Number;
  app_mode: Number;
  user_id: Number;
}

@Component({
  selector: 'app-home',
  standalone: true,
  imports: [CommonModule, ItemComponent, WebcamModule],
  templateUrl: './home.component.html',
  styleUrl: './home.component.css'
})
export class HomeComponent {
  title = 'Beer Ranking';
  componentTitle = "Beer Ranking";
  captureImageData:boolean = true
  refreshSubscription: any;
  observableSnapshot: any;
  wsSocketProtocol = location.protocol === 'http:' ? 'ws' : 'wss';
  editing = false;
  recognizedFaces:Array<Array<number>> = [];
  webCamArea:HTMLCanvasElement | null = null;

  wsSubject = webSocket(
    {
      url: this.wsSocketProtocol + '://' + location.hostname + ':8000/face-detection',
      binaryType: 'blob',
      serializer: v => v as Uint8ClampedArray,
    }
  );

  facingMode: string = 'user';
  allowCameraSwitch = false;

  public get videoOptions(): MediaTrackConstraints {
      const result: MediaTrackConstraints = {};
      if (this.facingMode && this.facingMode !== '') {
          result.facingMode = { ideal: this.facingMode };
      }
      return result;
  }

  refreshDrinkers(){
    var tempDrinkers:Drinker[] = [];
    this.drinksService.getDrinkers().subscribe(item => {
      item.forEach(drinker => {
        var temp = drinker;
        temp.quantity = temp.drinks!.reduce((accumulator,val) => accumulator+val.quantity,0)
        tempDrinkers.push(temp)
      });
      tempDrinkers.sort((a,b) => b.quantity - a.quantity);
      this.allDrinkers = tempDrinkers;
    });
  }

  constructor(private drinksService: DrinksService){
    this.refreshDrinkers();
    this.startIntervals();

    this.wsSubject.subscribe({
      next: (msg) => {
        if(typeof msg === "object" && msg && "faces" in msg)
          this.recognizedFaces = msg['faces'] as Array<Array<number>>;
        if(!this.webCamArea){
          this.webCamArea = document.getElementById("face-canvas") as HTMLCanvasElement;
          this.webCamArea.height = this.webCamArea.clientHeight;
          this.webCamArea.width = this.webCamArea.clientWidth;
        }
        else{
          let ctx = this.webCamArea.getContext('2d');
          if (ctx){
            ctx.beginPath();
            ctx.clearRect(0,0,this.webCamArea.width,this.webCamArea.height)

            if(typeof msg === "object" && msg && "app_state" in msg && "detected_face" in msg){
              let curr_mode = msg['app_state'] as DetectApp;
              if(curr_mode.app_mode == 1)
              {
                let quarterX = this.webCamArea.width*1.0/4;
                let quarterY = this.webCamArea.height*1.0/6;
                ctx.fillStyle = 'rgba(200, 0, 0, 0.5)';
                ctx.fillRect(0, 0, this.webCamArea.width, quarterY);
                ctx.fillRect(0, quarterY, quarterX, 4*quarterY);
                ctx.fillRect(3*quarterX, quarterY, quarterX, 4*quarterY);
                ctx.fillRect(0, 5*quarterY, this.webCamArea.width, quarterY);
              }
              for (const [x,y,width,height] of this.recognizedFaces){
                ctx.strokeStyle = "#49fb35";
                ctx.beginPath();
                ctx.rect(x,y,width,height);
                ctx.stroke();
              }
            }
          }
        }
      },
      error: (err) => console.log(err),
      complete: () => console.log("Connection closed")
      }
    )
  }

  startIntervals() {
    this.refreshSubscription = interval(5000).subscribe(
      val => {
        this.refreshDrinkers();
      }
    );

    this.observableSnapshot = new Observable<void>(
      observer => {
        setInterval(()=>{
                  observer.next(void 0);
                },500)
              }
        );
  }

  filter: "all" | "active" = "all";

  allDrinkers: Drinker[] = [
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
    if(flag)
    {
      this.refreshSubscription.unsubscribe()
    }
    else
    {
      this.refreshSubscription = interval(5000).subscribe(
        val => {
          this.refreshDrinkers();
        }
      );
    }
  }

  totalQuantity(): string{
    var total = this.drinkers.reduce((accumulator,val) => accumulator+val.quantity,0);
    return formatNumber(total/1000,"en-US","1.1-1");
  }

  getActiveUser(): string{
    var drinker = this.drinkers.filter(x => x.active == true);
    if(drinker.length > 0)
      return drinker[0].name;
    else
      return "";
  }

  get drinkers() {
    if (this.filter === "all") {
      return this.allDrinkers;
    }
    return this.allDrinkers.filter((item) => item.active);
  }

  private lastFrameData: Uint8ClampedArray | null = null;
  private lastSentTime: number = 0;
  private motionThreshold: number = 30;
  private minMotionPixels: number = 500;

  processCamSnapshot(camImage: WebcamImage){
    const now = Date.now();
    if (now - this.lastSentTime < 500) {
      return;
    }
    if (this.detectMotion(camImage)) {
      this.wsSubject.next(camImage.imageAsDataUrl);
      this.lastSentTime = now;
    }
  }

  private motionCanvas: HTMLCanvasElement = document.createElement('canvas');

  private detectMotion(camImage: WebcamImage): boolean {
    if (!this.lastFrameData) {
      this.updateLastFrame(camImage);
      return true;
    }
    const currentFrameData = this.getFrameData(camImage);
    if (!currentFrameData) return true;

    let diffCount = 0;
    for (let i = 0; i < currentFrameData.length; i += 4) {
      const rDiff = Math.abs(currentFrameData[i] - this.lastFrameData[i]);
      const gDiff = Math.abs(currentFrameData[i+1] - this.lastFrameData[i+1]);
      const bDiff = Math.abs(currentFrameData[i+2] - this.lastFrameData[i+2]);
      if ((rDiff + gDiff + bDiff) / 3 > this.motionThreshold) {
        diffCount++;
      }
    }
    this.lastFrameData = currentFrameData;
    return diffCount > this.minMotionPixels;
  }

  private updateLastFrame(camImage: WebcamImage) {
    this.lastFrameData = this.getFrameData(camImage);
  }

  private getFrameData(camImage: WebcamImage): Uint8ClampedArray | null {
    const ctx = this.motionCanvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return null;
    const width = camImage.imageData.width;
    const height = camImage.imageData.height;
    if (this.motionCanvas.width !== width || this.motionCanvas.height !== height) {
      this.motionCanvas.width = width;
      this.motionCanvas.height = height;
    }
    return camImage.imageData.data;
  }
}
