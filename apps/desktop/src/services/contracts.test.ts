import { describe, expect, it } from 'vitest';
import { requestSchema, responseSchema } from '@studynote/contracts';

describe('shared IPC protocol',()=>{
 it('rejects arbitrary shell execution, extra envelope fields and wrong versions',()=>{
   const request={protocol_version:1,id:'abc',method:'workspace.get',params:{}};
   expect(requestSchema.safeParse(request).success).toBe(true);
   for(const invalid of [{...request,method:'shell.execute'},{...request,protocol_version:2},{...request,key:'secret'}])expect(requestSchema.safeParse(invalid).success).toBe(false);
 });
 it('distinguishes successful responses and sanitized failures',()=>{
   expect(responseSchema.parse({protocol_version:1,id:'abc',ok:true,result:{saved:true}}).ok).toBe(true);
   expect(responseSchema.parse({protocol_version:1,id:'abc',ok:false,error:{code:'INVALID_REQUEST',message:'参数无效'}}).ok).toBe(false);
   expect(responseSchema.safeParse({protocol_version:1,id:'abc',ok:true,error:{}}).success).toBe(false);
 });
});
