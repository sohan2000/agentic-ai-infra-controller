import {createSlice} from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'

const initialState: any = {
    messages: []
}

const chatSlice = createSlice({
    name: "chat",
    initialState,
    reducers: {
        addMessage: (state, action: PayloadAction<any>) => {
            state.messages.push(action.payload)
        },
        clearMessages: (state) => {
            state.messages = []
        },
        setConversation: (state, action: PayloadAction<any[]>)=>{
            state.messages = action.payload
        }
    }    
})

export const {addMessage, clearMessages, setConversation} = chatSlice.actions
export default chatSlice.reducer