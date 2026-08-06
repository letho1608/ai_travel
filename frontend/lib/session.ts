let memorySession="";

function createSession():string{
  if(globalThis.crypto?.randomUUID)return globalThis.crypto.randomUUID();
  const bytes=new Uint8Array(16);
  if(globalThis.crypto?.getRandomValues)globalThis.crypto.getRandomValues(bytes);
  else for(let index=0;index<bytes.length;index++)bytes[index]=Math.floor(Math.random()*256);
  bytes[6]=(bytes[6]&15)|64;bytes[8]=(bytes[8]&63)|128;
  const hex=Array.from(bytes,value=>value.toString(16).padStart(2,"0")).join("");
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}

export function getSession():string{
  try{const stored=localStorage.getItem("ma_phien");if(stored){memorySession=stored;return stored}}catch{}
  if(!memorySession)memorySession=createSession();
  try{localStorage.setItem("ma_phien",memorySession)}catch{}
  return memorySession;
}

export function setSession(value:string):void{
  memorySession=value;
  try{localStorage.setItem("ma_phien",value)}catch{}
}
